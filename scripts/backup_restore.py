#!/usr/bin/env python3
"""
Utilitaires de sauvegarde et restauration pour PostgreSQL
"""
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
import shutil
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BACKUP_DIR = Path(__file__).parent.parent / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

def get_db_url() -> str:
    """Obtenir l'URL de la base de données"""
    from dotenv import load_dotenv
    load_dotenv()
    return os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/pfe_maintenance")

def parse_db_url(db_url: str) -> dict:
    """Parser l'URL PostgreSQL"""
    # Format: postgresql://user:password@host:port/database
    from urllib.parse import urlparse
    parsed = urlparse(db_url)
    return {
        "user": parsed.username,
        "password": parsed.password,
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/")
    }

def backup_database(backup_name: str = None) -> bool:
    """Sauvegarder la base de données PostgreSQL"""
    
    db_url = get_db_url()
    db_params = parse_db_url(db_url)
    
    if not backup_name:
        backup_name = f"pfe_maintenance_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    backup_file = BACKUP_DIR / f"{backup_name}.sql"
    
    logger.info(f"Sauvegarde en cours: {backup_file}")
    
    try:
        # Utiliser pg_dump
        env = os.environ.copy()
        env["PGPASSWORD"] = db_params["password"]
        
        cmd = [
            "pg_dump",
            "-h", db_params["host"],
            "-p", str(db_params["port"]),
            "-U", db_params["user"],
            "-d", db_params["database"],
            "-v",  # Verbose
            "-f", str(backup_file)
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Erreur pg_dump: {result.stderr}")
            return False
        
        file_size = backup_file.stat().st_size / (1024 * 1024)  # MB
        logger.info(f"✓ Sauvegarde réussie: {file_size:.2f} MB")
        logger.info(f"  Fichier: {backup_file}")
        
        return True
    
    except Exception as e:
        logger.error(f"✗ Erreur sauvegarde: {e}")
        return False

def restore_database(backup_file: str, force: bool = False) -> bool:
    """Restaurer la base de données depuis une sauvegarde"""
    
    backup_path = Path(backup_file)
    
    if not backup_path.exists():
        # Chercher dans le répertoire backups
        backup_path = BACKUP_DIR / backup_file
        if not backup_path.exists():
            logger.error(f"Fichier non trouvé: {backup_file}")
            return False
    
    db_url = get_db_url()
    db_params = parse_db_url(db_url)
    
    if not force:
        response = input(f"⚠️  Confirmer restauration depuis {backup_path.name}? (y/n): ")
        if response.lower() != 'y':
            logger.info("Restauration annulée")
            return False
    
    logger.info(f"Restauration en cours depuis: {backup_path}")
    
    try:
        env = os.environ.copy()
        env["PGPASSWORD"] = db_params["password"]
        
        # D'abord, drop et recreate la base
        logger.info("Recréation de la base de données...")
        
        drop_cmd = [
            "psql",
            "-h", db_params["host"],
            "-p", str(db_params["port"]),
            "-U", db_params["user"],
            "-d", "postgres",
            "-c", f"DROP DATABASE IF EXISTS {db_params['database']};"
        ]
        
        create_cmd = [
            "psql",
            "-h", db_params["host"],
            "-p", str(db_params["port"]),
            "-U", db_params["user"],
            "-d", "postgres",
            "-c", f"CREATE DATABASE {db_params['database']};"
        ]
        
        subprocess.run(drop_cmd, env=env, capture_output=True)
        subprocess.run(create_cmd, env=env, capture_output=True)
        
        # Restaurer depuis la sauvegarde
        logger.info("Restauration des données...")
        
        with open(backup_path, 'r') as f:
            restore_cmd = [
                "psql",
                "-h", db_params["host"],
                "-p", str(db_params["port"]),
                "-U", db_params["user"],
                "-d", db_params["database"],
            ]
            
            result = subprocess.run(restore_cmd, stdin=f, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Erreur restauration: {result.stderr}")
            return False
        
        logger.info("✓ Restauration réussie")
        return True
    
    except Exception as e:
        logger.error(f"✗ Erreur restauration: {e}")
        return False

def list_backups():
    """Lister les sauvegardes disponibles"""
    
    logger.info(f"Sauvegardes disponibles dans {BACKUP_DIR}:\n")
    
    backups = sorted(BACKUP_DIR.glob("*.sql"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not backups:
        logger.info("Aucune sauvegarde trouvée")
        return
    
    for idx, backup in enumerate(backups, 1):
        size = backup.stat().st_size / (1024 * 1024)  # MB
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"{idx}. {backup.name}")
        print(f"   Taille: {size:.2f} MB | Date: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

def cleanup_old_backups(keep_count: int = 5):
    """Supprimer les anciennes sauvegardes"""
    
    backups = sorted(BACKUP_DIR.glob("*.sql"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if len(backups) > keep_count:
        to_delete = backups[keep_count:]
        logger.info(f"Suppression de {len(to_delete)} anciennes sauvegardes...")
        
        for backup in to_delete:
            backup.unlink()
            logger.info(f"  Supprimée: {backup.name}")
        
        logger.info(f"✓ Conservation de {keep_count} sauvegardes")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Utilitaires de sauvegarde/restauration PostgreSQL"
    )
    parser.add_argument("action", choices=["backup", "restore", "list", "cleanup"],
                       help="Action à effectuer")
    parser.add_argument("--backup-name", help="Nom de la sauvegarde (pour backup)")
    parser.add_argument("--file", help="Fichier de sauvegarde (pour restore)")
    parser.add_argument("--force", action="store_true", help="Forcer sans confirmer")
    parser.add_argument("--keep", type=int, default=5, help="Nombre de sauvegardes à conserver")
    
    args = parser.parse_args()
    
    if args.action == "backup":
        success = backup_database(args.backup_name)
        sys.exit(0 if success else 1)
    
    elif args.action == "restore":
        if not args.file:
            logger.error("--file requis pour restore")
            sys.exit(1)
        success = restore_database(args.file, args.force)
        sys.exit(0 if success else 1)
    
    elif args.action == "list":
        list_backups()
    
    elif args.action == "cleanup":
        cleanup_old_backups(args.keep)
