"""
Assistant RAG pour la maintenance predictive ONEE.

Cette implementation reste volontairement legere: elle fonctionne sans service
externe, puis utilise Groq automatiquement si GROQ_API_KEY est disponible.
"""
import hashlib
import json
import logging
import math
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from dotenv import load_dotenv

# Le fichier .env du projet doit remplacer une ancienne valeur héritée du terminal
# (notamment une clé d'exemple chargée avant le démarrage de Streamlit).
load_dotenv(override=True)
logging.getLogger("chromadb.telemetry.product.posthog").disabled = True


class LocalHashEmbeddingFunction:
    """Embeddings locaux, deterministes et sans telechargement externe."""

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def __call__(self, input: List[str]) -> List[List[float]]:
        return [self._embed(text) for text in input]

    @staticmethod
    def name() -> str:
        return "local_hash_384"

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        tokens = RAGChatbot._tokens(text)

        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if not norm:
            return vector
        return [value / norm for value in vector]


class SemanticEmbeddingFunction:
    """Embeddings sémantiques multilingues compatibles avec ChromaDB."""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def __call__(self, input: List[str]) -> List[List[float]]:
        vectors = self.model.encode(input, normalize_embeddings=True)
        return vectors.tolist()

    def name(self) -> str:
        return f"sentence_transformer_{self.model_name.replace('/', '_')}"


class RAGChatbot:
    """Chatbot RAG avec ChromaDB, retrieval semantique et fallback local."""

    def __init__(
        self,
        provider: str = "groq",
        model: str = "openai/gpt-oss-120b",
        persist_dir: Optional[str] = None,
        collection_name: str = "onee_maintenance_knowledge_v3",
    ):
        self.requested_provider = provider
        self.llm_provider = "local"
        self.model = model
        self.documents: List[Dict[str, str]] = []
        self.vectorstore = None
        self.response_cache: Dict[str, Dict] = {}
        self.groq_client = None
        self.persist_dir = Path(persist_dir or os.getenv("RAG_CHROMA_DIR", "chroma_db/rag_knowledge_v2"))
        self.collection_name = collection_name
        semantic_model = os.getenv(
            "RAG_EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        semantic_enabled = os.getenv("RAG_SEMANTIC_EMBEDDINGS", "false").lower() in {
            "1", "true", "yes", "on",
        }
        if semantic_enabled:
            try:
                self.embedding_function = SemanticEmbeddingFunction(semantic_model)
                self.embedding_model = semantic_model
            except Exception:
                logging.getLogger(__name__).warning(
                    "Embeddings sémantiques indisponibles, repli sur local_hash_384"
                )
                self.embedding_function = LocalHashEmbeddingFunction()
                self.embedding_model = "local_hash_384"
        else:
            self.embedding_function = LocalHashEmbeddingFunction()
            self.embedding_model = "local_hash_384"
        self.chroma_client = None
        self.collection = None

        self._init_vectorstore()

        groq_key = (os.getenv("GROQ_API_KEY") or "").strip()
        key_is_configured = groq_key.startswith("gsk_") and not any(
            marker in groq_key.lower() for marker in ("your", "example", "change", "api-key")
        )
        if provider == "groq" and key_is_configured:
            try:
                from groq import Groq

                self.groq_client = Groq(api_key=groq_key)
                self.llm_provider = "groq"
            except Exception:
                self.groq_client = None
                self.llm_provider = "local"

    def add_knowledge_base(self, documents: List[Dict[str, str]]) -> None:
        """Indexe les documents dans ChromaDB et garde une copie en memoire."""
        self.documents = self._normalize_documents(documents or [])
        if not self.documents:
            return

        self._ensure_vectorstore()
        if self.collection is None:
            self.vectorstore = None
            self.response_cache.clear()
            return

        ids = [self._document_id(doc) for doc in self.documents]
        contents = [self._document_text(doc) for doc in self.documents]
        metadatas = [self._document_metadata(doc) for doc in self.documents]

        self.collection.upsert(
            ids=ids,
            documents=contents,
            metadatas=metadatas,
        )
        # La collection represente exactement le corpus courant : retirer les
        # anciens vecteurs afin que le compteur et les sources restent fiables.
        try:
            stored_ids = set((self.collection.get(include=[]) or {}).get("ids", []))
            stale_ids = list(stored_ids - set(ids))
            if stale_ids:
                self.collection.delete(ids=stale_ids)
        except Exception:
            logger.exception("Impossible de nettoyer les anciens vecteurs RAG")
        self.vectorstore = self.collection
        self.response_cache.clear()

    def load_knowledge_base_from_db(self, db) -> int:
        """Charge la table knowledge_base si elle contient des documents actifs."""
        from backend.models import KnowledgeBase

        rows = db.query(KnowledgeBase).all()
        documents = []
        for row in rows:
            documents.append({
                "id": str(row.id),
                "document_title": row.document_title,
                "document_type": "knowledge",
                "equipment_type": row.equipment_type.name if row.equipment_type else "general",
                "tags": "",
                "content": row.content,
            })

        if documents:
            self.add_knowledge_base(documents)
        return len(documents)

    def get_knowledge_stats(self) -> Dict[str, object]:
        vector_count = 0
        if self.collection:
            try:
                vector_count = self.collection.count()
            except Exception:
                vector_count = 0

        return {
            "documents_count": len(self.documents),
            "has_vectorstore": bool(self.vectorstore),
            "vector_documents_count": vector_count,
            "has_llm": self.llm_provider == "groq",
            "provider": self.llm_provider,
            "cache_size": len(self.response_cache),
            "retriever": "chromadb",
            "embedding_model": self.embedding_model,
        }

    def get_stats(self) -> Dict[str, object]:
        return self.get_knowledge_stats()

    def query(
        self,
        question: str,
        equipment_context: Optional[Dict] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        platform_context: Optional[Dict] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Dict:
        """Router une demande entre conversation, plateforme et recherche RAG."""
        started_at = time.time()
        normalized_question = self._normalize(question)
        history = (chat_history or [])[-10:]
        context_key = self._context_key(equipment_context) + self._context_key(platform_context)
        history_key = "|".join(
            f"{item.get('role', '')}:{item.get('content', '')}" for item in history
        )
        cache_key = hashlib.sha256(f"{normalized_question}|{context_key}|{history_key}".encode()).hexdigest()

        if cache_key in self.response_cache:
            cached = dict(self.response_cache[cache_key])
            cached["cached"] = True
            cached["response_time"] = round(time.time() - started_at, 4)
            return cached

        query_tokens = set(self._tokens(question))
        needs_rag = self._is_domain_question(query_tokens)
        sources = []
        if needs_rag:
            if not self.documents:
                self.add_knowledge_base(generate_default_knowledge_base())
            sources = self._filter_relevant_sources(question, self._retrieve(question, limit=4))

        answer = self._generate_unified_answer(
            question=question,
            chat_history=history,
            sources=sources,
            equipment_context=equipment_context,
            platform_context=platform_context,
            on_token=on_token,
        )
        if platform_context and sources:
            mode = "platform+rag"
        elif platform_context:
            mode = "platform"
        elif sources:
            mode = "rag"
        else:
            mode = "general"

        response = {
            "answer": answer,
            "sources": [
                {
                    "title": doc.get("document_title", "Document technique"),
                    "content": self._source_caption(doc),
                    "type": doc.get("document_type", "knowledge"),
                    "equipment_type": doc.get("equipment_type", "general"),
                    "score": doc.get("score"),
                }
                for doc in sources
            ],
            "confidence": self._estimate_confidence(question, sources) if sources else (0.95 if platform_context else 0.8),
            "cached": False,
            "provider": self.llm_provider,
            "mode": mode,
            "response_time": round(time.time() - started_at, 4),
        }
        self.response_cache[cache_key] = response
        return response

    def _retrieve(self, question: str, limit: int = 3) -> List[Dict[str, str]]:
        self._ensure_vectorstore()
        if not self.vectorstore:
            return self._lexical_fallback(question, limit=limit)

        try:
            result = self.collection.query(
                query_texts=[question],
                n_results=limit,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return self._lexical_fallback(question, limit=limit)

        metadatas = result.get("metadatas", [[]])[0] or []
        documents = result.get("documents", [[]])[0] or []
        distances = result.get("distances", [[]])[0] or []

        sources = []
        for metadata, content, distance in zip(metadatas, documents, distances):
            doc = dict(metadata or {})
            doc["content"] = doc.pop("raw_content", None) or content or ""
            doc["score"] = self._distance_to_score(distance)
            sources.append(doc)

        if not sources:
            return self._lexical_fallback(question, limit=limit)
        return sources

    def _filter_relevant_sources(self, question: str, sources: List[Dict[str, str]]) -> List[Dict[str, str]]:
        if not sources:
            return []

        query_tokens = set(self._tokens(question))
        if not query_tokens:
            return []

        if not self._is_domain_question(query_tokens):
            return []

        target_equipment = self._target_equipment(query_tokens)
        filtered = []
        for doc in sources:
            score = doc.get("score")
            doc_tokens = set(self._tokens(
                " ".join(str(doc.get(field, "")) for field in ("document_title", "equipment_type", "tags", "content"))
            ))
            equipment_type = self._normalize(doc.get("equipment_type", ""))
            has_overlap = bool(query_tokens & doc_tokens)
            strong_score = isinstance(score, float) and score >= 0.36
            if has_overlap or strong_score:
                if isinstance(score, float):
                    doc["score"] = self._rerank_score(score, doc_tokens, query_tokens, equipment_type, target_equipment)
                filtered.append(doc)

        filtered.sort(key=lambda doc: doc.get("score") or 0, reverse=True)
        if target_equipment:
            exact = [doc for doc in filtered if self._normalize(doc.get("equipment_type", "")) == target_equipment]
            if exact:
                strong_related = [
                    doc for doc in filtered
                    if doc not in exact and isinstance(doc.get("score"), float) and doc["score"] >= 0.50
                ]
                return exact + strong_related
        return filtered

    def _target_equipment(self, query_tokens: set) -> Optional[str]:
        equipment_terms = {
            "turbine", "chaudiere", "alternateur", "condenseur",
            "compresseur", "pompe", "echangeur",
        }
        for term in equipment_terms:
            if term in query_tokens:
                return term
        return None

    def _rerank_score(
        self,
        score: float,
        doc_tokens: set,
        query_tokens: set,
        equipment_type: str,
        target_equipment: Optional[str],
    ) -> float:
        lexical_overlap = len(query_tokens & doc_tokens) / max(len(query_tokens), 1)
        adjusted = score + lexical_overlap * 0.25
        if target_equipment and equipment_type == target_equipment:
            adjusted += 0.35
        elif target_equipment and equipment_type != target_equipment:
            adjusted -= 0.20
        return max(0.0, min(0.99, adjusted))

    def _init_vectorstore(self) -> None:
        try:
            import chromadb
            from chromadb.config import Settings

            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(anonymized_telemetry=False),
            )
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"description": "Base RAG maintenance predictive ONEE"},
            )
            self.vectorstore = self.collection if self.collection.count() else None
        except Exception:
            self.chroma_client = None
            self.collection = None
            self.vectorstore = None

    def _ensure_vectorstore(self) -> None:
        if self.collection is None:
            self._init_vectorstore()

    def _normalize_documents(self, documents: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
        normalized = []
        for index, doc in enumerate(documents):
            content = str(doc.get("content", "")).strip()
            if not content:
                continue

            normalized.append({
                "id": str(doc.get("id") or doc.get("document_id") or index),
                "document_title": str(doc.get("document_title") or doc.get("title") or "Document technique"),
                "document_type": str(doc.get("document_type") or "knowledge"),
                "equipment_type": str(doc.get("equipment_type") or "general"),
                "tags": str(doc.get("tags") or ""),
                "content": content,
            })
        return normalized

    def _document_id(self, doc: Dict[str, str]) -> str:
        raw_id = "|".join([
            str(doc.get("id", "")),
            doc.get("document_title", ""),
            doc.get("equipment_type", ""),
            doc.get("content", "")[:200],
        ])
        return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()

    def _document_text(self, doc: Dict[str, str]) -> str:
        return "\n".join([
            f"Titre: {doc.get('document_title', '')}",
            f"Type: {doc.get('document_type', '')}",
            f"Equipement: {doc.get('equipment_type', '')}",
            f"Tags: {doc.get('tags', '')}",
            "",
            doc.get("content", ""),
        ])

    def _document_metadata(self, doc: Dict[str, str]) -> Dict[str, str]:
        return {
            "document_title": doc.get("document_title", "Document technique"),
            "document_type": doc.get("document_type", "knowledge"),
            "equipment_type": doc.get("equipment_type", "general"),
            "tags": doc.get("tags", ""),
            "raw_content": doc.get("content", ""),
        }

    def _lexical_fallback(self, question: str, limit: int = 3) -> List[Dict[str, str]]:
        query_tokens = set(self._tokens(question))
        scored = []

        for doc in self.documents:
            searchable = " ".join(
                str(doc.get(field, ""))
                for field in ("document_title", "document_type", "equipment_type", "tags", "content")
            )
            doc_tokens = set(self._tokens(searchable))
            score = len(query_tokens & doc_tokens)
            if score:
                enriched_doc = dict(doc)
                enriched_doc["score"] = min(0.95, 0.35 + score / max(len(query_tokens), 1))
                scored.append((score, enriched_doc))

        if not scored:
            return self.documents[:limit]

        scored.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored[:limit]]

    @staticmethod
    def _distance_to_score(distance) -> float:
        try:
            value = float(distance)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(0.99, 1.0 / (1.0 + value)))

    def _generate_unified_answer(
        self,
        question: str,
        chat_history: List[Dict[str, str]],
        sources: List[Dict[str, str]],
        equipment_context: Optional[Dict],
        platform_context: Optional[Dict],
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Produire une réponse unique à partir de la conversation et des contextes disponibles."""
        context_sections = []
        if equipment_context:
            context_sections.append(
                "CONTEXTE ÉQUIPEMENT:\n" + json.dumps(equipment_context, ensure_ascii=False, default=str)
            )
        if platform_context:
            context_sections.append(
                "DONNÉES DE LA PLATEFORME:\n"
                + json.dumps(platform_context, ensure_ascii=False, default=str)
            )
        if sources:
            documents = []
            for source in sources:
                documents.append(
                    f"Titre: {source.get('document_title', 'Document technique')}\n"
                    f"Contenu: {source.get('content', '')[:1400]}"
                )
            context_sections.append("DOCUMENTS RAG:\n" + "\n\n".join(documents))

        available_context = "\n\n".join(context_sections) or "Aucun contexte technique particulier."
        prompt = f"""
Réponds naturellement à l'utilisateur.

Tu es l'assistant intelligent intégré à une plateforme de maintenance
prédictive industrielle ONEE.

Tu peux :
- discuter normalement avec l'utilisateur ;
- retenir le contexte de la conversation ;
- répondre aux questions générales ;
- utiliser les données de la plateforme lorsqu'elles existent ;
- utiliser les documents techniques fournis pour les questions métier.

IMPORTANT :
- N'invente jamais une mesure, une alerte, une anomalie ou une valeur RUL.
- Les données de la plateforme ont priorité pour les valeurs réelles.
- Les documents techniques servent à expliquer et recommander.
- Ne parle jamais de ton architecture interne.
- Ne mentionne pas Groq, RAG ou PostgreSQL sauf si l'utilisateur le demande.
- Réponds principalement en français.
- Reste synthétique : utilise au maximum 5 étapes ou points principaux.
- Évite les répétitions, les longues introductions et les détails non demandés.
- Termine toujours la dernière phrase proprement ; raccourcis la réponse si nécessaire.

CONTEXTE DISPONIBLE :
{available_context}

QUESTION :
{question}
"""
        generated = self._call_llm(prompt, chat_history, on_token=on_token)
        if generated:
            return generated
        return "Le service conversationnel est temporairement indisponible. Veuillez réessayer dans quelques instants."

    def _call_llm(
        self,
        prompt: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        if not self.groq_client:
            return None
        try:
            request = {
                "model": self.model,
                "messages": self._llm_messages(prompt, chat_history),
                "temperature": 0.2,
                "max_tokens": 1000,
            }
            if on_token:
                stream = self.groq_client.chat.completions.create(**request, stream=True)
                chunks = []
                for event in stream:
                    token = event.choices[0].delta.content or ""
                    if token:
                        chunks.append(token)
                        on_token(token)
                return "".join(chunks).strip()

            completion = self.groq_client.chat.completions.create(**request)
            return completion.choices[0].message.content.strip()
        except Exception as error:
            logging.getLogger(__name__).exception("Erreur lors de l'appel Groq: %r", error)
            return None

    @staticmethod
    def _llm_messages(prompt: str, chat_history: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
        messages = [{
            "role": "system",
            "content": (
                "Tu es un assistant intelligent intégré à une plateforme de maintenance prédictive "
                "industrielle. Tu es naturel, conversationnel, précis et professionnel. Tu peux discuter "
                "normalement, répondre à des questions générales et expliquer des notions techniques. "
                "Utilise l'historique pour comprendre les références aux messages précédents et mémoriser "
                "les informations données par l'utilisateur pendant cette discussion. Ne répète pas ton "
                "rôle et ne donne pas de réponse générique si la demande est compréhensible. N'invente "
                "jamais une mesure, une anomalie, une alerte ou une valeur RUL. Réponds principalement en "
                "français et adapte la longueur ainsi que le niveau technique à la question."
            ),
        }]
        for item in (chat_history or [])[-12:]:
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                messages.append({"role": item["role"], "content": str(item["content"])[:1800]})
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _compact_content(content: str) -> str:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return "Aucun detail disponible."

        formatted = []
        for line in lines[:14]:
            if line.endswith(":"):
                if formatted:
                    formatted.append("")
                formatted.append(f"**{line}**")
            elif re.match(r"^\d+\.", line):
                formatted.append(line)
            elif line.startswith("-"):
                formatted.append(line)
            else:
                formatted.append(line)

        return "\n".join(formatted)

    @staticmethod
    def _source_caption(doc: Dict[str, str]) -> str:
        title = doc.get("document_title", "Document technique")
        equipment_type = doc.get("equipment_type", "general")
        excerpt = RAGChatbot._compact_content(doc.get("content", "")).replace("\n", " ")
        return f"{title} ({equipment_type}) - {excerpt[:220]}"

    def _estimate_confidence(self, question: str, sources: List[Dict[str, str]]) -> float:
        if not sources:
            return 0.35

        scores = [doc.get("score") for doc in sources if isinstance(doc.get("score"), float)]
        if scores:
            return min(0.95, max(0.35, sum(scores[:3]) / min(len(scores), 3)))

        query_tokens = set(self._tokens(question))
        source_tokens = set()
        for doc in sources:
            source_tokens.update(
                self._tokens(
                    " ".join(
                        str(doc.get(field, ""))
                        for field in ("document_title", "equipment_type", "tags", "content")
                    )
                )
            )

        if not query_tokens:
            return 0.5

        overlap = len(query_tokens & source_tokens) / max(len(query_tokens), 1)
        return min(0.95, max(0.45, 0.55 + overlap * 0.35))

    def _is_domain_question(self, query_tokens: set) -> bool:
        domain_terms = {
            "maintenance", "predictive", "predictive", "onee", "centrale", "thermique",
            "turbine", "chaudiere", "alternateur", "condenseur", "compresseur", "pompe",
            "echangeur", "capteur", "temperature", "pression", "vibration", "debit",
            "courant", "tension", "stator", "palier", "rotor", "roulement", "anomalie",
            "alerte", "rul", "inspection", "diagnostic", "seuil", "criticite", "critique",
            "panne", "fuite", "vapeur", "refroidissement", "alignement", "charge",
            "frequence", "huile", "soupape", "eau", "vide", "procedure", "info",
            "dxm", "circuit", "schema", "documentation", "document", "graissage",
            "charbon", "fumee", "combustion", "transformateur", "fonctionnement",
        }
        expanded_tokens = set(query_tokens)
        for token in query_tokens:
            expanded_tokens.update(self._token_variants(token))
        return bool(expanded_tokens & domain_terms)

    @staticmethod
    def _format_equipment_context(context: Optional[Dict]) -> str:
        if not context:
            return "Non fourni"
        return ", ".join(f"{key}={value}" for key, value in context.items())

    @staticmethod
    def _normalize(text: str) -> str:
        text = unicodedata.normalize("NFKD", text or "")
        text = "".join(char for char in text if not unicodedata.combining(char))
        return re.sub(r"\s+", " ", text.strip().lower())

    @staticmethod
    def _tokens(text: str) -> List[str]:
        normalized = RAGChatbot._normalize(text)
        tokens = []
        for token in re.findall(r"[a-zA-Z0-9_]+", normalized):
            tokens.extend(RAGChatbot._token_variants(token))
        return list(dict.fromkeys(tokens))

    @staticmethod
    def _token_variants(token: str) -> List[str]:
        variants = [token]
        if len(token) > 3 and token.endswith("s"):
            variants.append(token[:-1])
        if token in {"infos", "information", "informations"}:
            variants.append("info")
        if token in {"chaudieres", "chaudières"}:
            variants.append("chaudiere")
        if token in {"equipements", "équipements"}:
            variants.append("equipement")
        return variants

    @staticmethod
    def _context_key(context: Optional[Dict]) -> str:
        if not context:
            return ""
        return "|".join(f"{key}:{context[key]}" for key in sorted(context))


IndustrialRAGChatbot = RAGChatbot


def generate_default_knowledge_base() -> List[Dict[str, str]]:
    """Corpus technique de demonstration compose de 24 procedures distinctes."""
    documents = [
        {
            "document_title": "Turbine Vapeur - Diagnostic Vibration",
            "document_type": "procedure",
            "equipment_type": "Turbine",
            "tags": "turbine,vibration,rotor,roulement,temperature,pression,alerte,signe,diagnostic",
            "content": """
Signaux critiques:
- Vibration superieure a 8 mm/s
- Temperature superieure a 410 C
- Pression inferieure a 100 bar

Causes possibles:
- Desalignement rotor
- Roulements uses
- Desequilibre mecanique

Actions:
1. Verifier les roulements
2. Controler l'alignement
3. Reduire temporairement la charge turbine
4. Planifier une inspection
""",
        },
        {
            "document_title": "Chaudiere Industrielle",
            "document_type": "procedure",
            "equipment_type": "Chaudiere",
            "tags": "chaudiere,temperature,pression,vapeur,debit,eau",
            "content": """
Plage normale:
- Temperature foyer: 800 C a 1100 C
- Pression vapeur: 120 a 250 bar

Alertes typiques:
- Temperature excessive
- Fuite vapeur
- Baisse du debit d'eau d'alimentation

Actions:
1. Verifier les echangeurs
2. Controler la circulation d'eau
3. Inspecter les soupapes
4. Nettoyer les tubes si encrassement
""",
        },
        {
            "document_title": "Alternateur - Surveillance Electrique",
            "document_type": "procedure",
            "equipment_type": "Alternateur",
            "tags": "alternateur,stator,palier,courant,tension,vibration",
            "content": """
Points de surveillance:
- Temperature stator elevee
- Vibration palier anormale
- Variation courant ou tension sortie

Actions:
1. Controler le refroidissement du stator
2. Inspecter les paliers
3. Verifier les connexions electriques
4. Reduire la charge si la temperature continue de monter
""",
        },
        {
            "document_title": "Condenseur - Vide et Refroidissement",
            "document_type": "procedure",
            "equipment_type": "Condenseur",
            "tags": "condenseur,vide,temperature,eau,debit,refroidissement",
            "content": """
Indicateurs importants:
- Vide condenseur degrade
- Temperature sortie eau elevee
- Debit circulation insuffisant

Actions:
1. Verifier les pompes de circulation
2. Inspecter l'encrassement des tubes
3. Controler les entrees d'air parasites
4. Nettoyer le circuit de refroidissement
""",
        },
    ]

    additional_procedures = [
        ("Turbine - Contrôle des paliers", "Turbine", "palier,huile,temperature,jeu",
         "Contrôler la température des paliers, la pression et la propreté de l’huile. Rechercher tout jeu, bruit ou échauffement anormal. En cas de dérive persistante, réduire la charge et programmer une inspection."),
        ("Turbine - Procédure d'arrêt d'urgence", "Turbine", "arret,urgence,securite,vapeur",
         "Déclencher l’arrêt selon la procédure du site, isoler l’admission vapeur, vérifier la décélération du rotor et sécuriser la zone. Consigner les événements et interdire le redémarrage avant autorisation."),
        ("Turbine - Contrôle de l'huile", "Turbine", "huile,lubrification,filtre,pression",
         "Vérifier niveau, pression, température, coloration et contamination de l’huile. Contrôler les filtres et rechercher les fuites. Une pression insuffisante impose une réduction de charge immédiate."),
        ("Chaudière - Contrôle combustion", "Chaudiere", "combustion,foyer,oxygene,bruleur",
         "Surveiller la stabilité de flamme, l’oxygène résiduel, la température du foyer et les fumées. Inspecter les brûleurs et corriger le rapport air-combustible avant retour au régime nominal."),
        ("Chaudière - Niveau d'eau critique", "Chaudiere", "niveau,eau,vapeur,securite",
         "Comparer les indicateurs redondants de niveau. En niveau bas confirmé, sécuriser la combustion selon la procédure d’urgence. Ne jamais réalimenter brutalement une chaudière potentiellement surchauffée."),
        ("Chaudière - Inspection des soupapes", "Chaudiere", "soupape,pression,securite,tarage",
         "Contrôler l’étanchéité, le tarage, les scellés et la ligne de décharge des soupapes. Documenter chaque essai et remplacer toute soupape qui ne revient pas correctement en position fermée."),
        ("Alternateur - Refroidissement stator", "Alternateur", "stator,refroidissement,temperature,ventilation",
         "Vérifier ventilateurs, échangeurs, filtres et températures des enroulements. Comparer les phases. Une hausse homogène indique souvent un défaut de refroidissement ou une surcharge."),
        ("Alternateur - Déséquilibre des phases", "Alternateur", "phase,courant,tension,desequilibre",
         "Comparer tensions et courants des trois phases, contrôler les connexions et la charge. Réduire la charge si le déséquilibre dépasse les limites d’exploitation et rechercher le défaut en aval."),
        ("Alternateur - Contrôle d'isolement", "Alternateur", "isolement,enroulement,megohmetre,securite",
         "Mettre l’équipement hors tension, consigner et vérifier l’absence de tension. Mesurer la résistance d’isolement selon la procédure constructeur et corriger la valeur en fonction de la température."),
        ("Condenseur - Recherche de fuite d'air", "Condenseur", "vide,fuite,air,etancheite",
         "Contrôler les brides, joints, presse-étoupes et lignes sous vide. Utiliser la méthode de détection autorisée sur site. Localiser puis réparer toute entrée d’air avant d’augmenter la charge."),
        ("Condenseur - Nettoyage des tubes", "Condenseur", "tube,encrassement,eau,nettoyage",
         "Isoler et consigner le circuit, inspecter l’encrassement et appliquer la méthode de nettoyage compatible avec les tubes. Vérifier l’intégrité et le débit après remise en service."),
        ("Pompe - Cavitation", "Pompe", "pompe,cavitation,pression,vibration,debit",
         "Rechercher bruit de graviers, vibration et débit instable. Vérifier pression d’aspiration, niveau de bâche, température du fluide et obstruction. Réduire le débit si nécessaire."),
        ("Pompe - Alignement moteur-pompe", "Pompe", "alignement,accouplement,vibration,palier",
         "Consigner l’ensemble, contrôler le pied boiteux puis réaliser l’alignement parallèle et angulaire. Resserrer au couple et confirmer par une mesure vibratoire après redémarrage."),
        ("Pompe - Garniture mécanique", "Pompe", "garniture,fuite,etancheite,temperature",
         "Contrôler fuite, température et alimentation du plan de rinçage. Une fuite croissante impose de préparer l’arrêt et le remplacement de la garniture selon les règles de sécurité."),
        ("Compresseur - Température de refoulement", "Compresseur", "compresseur,temperature,refoulement,refroidissement",
         "Vérifier refroidisseurs, lubrification, pression d’aspiration et encrassement. Une température de refoulement élevée peut dégrader l’huile et exige une réduction de charge."),
        ("Compresseur - Filtration d'air", "Compresseur", "filtre,air,pression,maintenance",
         "Contrôler la perte de charge et l’état des éléments filtrants. Remplacer les filtres colmatés, nettoyer le logement et vérifier l’absence d’entrée d’air non filtré."),
        ("Échangeur - Perte de performance", "Echangeur", "echangeur,temperature,debit,encrassement",
         "Comparer les températures d’entrée et sortie ainsi que les débits. Une baisse du coefficient d’échange suggère encrassement, dérivation interne ou débit insuffisant."),
        ("Capteurs - Validation d'une mesure", "Instrumentation", "capteur,etalonnage,mesure,derive",
         "Comparer la mesure à un instrument de référence et aux capteurs redondants. Vérifier câblage, alimentation et unité. Ne pas acquitter une alerte sur la seule hypothèse d’un capteur défectueux."),
        ("Alertes - Traitement d'une alerte critique", "General", "alerte,critique,acquittement,ordre",
         "Identifier l’équipement, confirmer la mesure et appliquer les actions de mise en sécurité. Acquitter avec commentaire, créer un ordre prioritaire et conserver les preuves de diagnostic."),
        ("Maintenance - Consignation électrique", "General", "consignation,electrique,securite,intervention",
         "Identifier toutes les sources, arrêter, isoler, condamner et vérifier l’absence de tension. Poser la mise à la terre lorsque requise. Seul le personnel habilité peut déconsigner."),
    ]
    for title, equipment, tags, content in additional_procedures:
        documents.append({
            "document_title": title,
            "document_type": "procedure",
            "equipment_type": equipment,
            "tags": tags,
            "content": content,
        })

    external_corpus = Path(__file__).resolve().parents[1] / "knowledge_documents" / "rag_documents.json"
    if external_corpus.exists():
        try:
            external_documents = json.loads(external_corpus.read_text(encoding="utf-8"))
            if isinstance(external_documents, list):
                documents.extend(external_documents)
        except (OSError, json.JSONDecodeError):
            logging.getLogger(__name__).exception(
                "Impossible de charger le corpus RAG externe %s", external_corpus
            )
    return documents


if __name__ == "__main__":
    chatbot = RAGChatbot()
    chatbot.add_knowledge_base(generate_default_knowledge_base())
    print(chatbot.get_stats())

    while True:
        question = input("\nQuestion: ")
        if question.lower() == "exit":
            break
        print(chatbot.query(question)["answer"])
