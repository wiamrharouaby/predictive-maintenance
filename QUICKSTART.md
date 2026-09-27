# ⚡ Quickstart - 5 Minutes

## 1️⃣ Prérequis
```bash
# Vérifier Python 3.8+
python --version

# Vérifier PostgreSQL
psql --version
```

## 2️⃣ Setup (2 min)
```bash
# Clone & venv
git clone <repo>
cd pfe-maintenance-predictive
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows

# Install dependencies
pip install -r requirements.txt

# Create database
createdb pfe_maintenance
```

## 3️⃣ Configuration (1 min)
```bash
# Setup .env
cp .env.example .env

# Edit .env:
# DATABASE_URL=postgresql://postgres:password@localhost:5432/pfe_maintenance
# SECRET_KEY=any-secret-key-at-least-32-chars
```

## 4️⃣ Initialize (1 min)
```bash
python scripts/init_db.py
```

## 5️⃣ Run (1 min)
```bash
./run.sh
```

Or manually:
```bash
# Terminal 1
python -m uvicorn backend.main:app --reload

# Terminal 2
streamlit run streamlit_app.py
```

## 🎯 Access
- **Dashboard**: http://localhost:8501
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## 🔑 Login
```
Username: admin
Password: admin123
```

## ✅ Verify

- [ ] Dashboard loads
- [ ] Can login
- [ ] See 4 metrics on dashboard
- [ ] View equipment in monitoring
- [ ] See predictions
- [ ] Chat with bot works

## 📚 Next Steps

1. Check out `README.md` for full documentation
2. Run `python test_complete.py` to validate everything
3. Read `PROJECT_SUMMARY.md` for architecture overview
4. See `INTEGRATION_GUIDE.md` for testing procedures

## 🆘 Common Issues

### Port already in use
```bash
# Change port in .env
STREAMLIT_PORT=8502
# or kill process:
lsof -ti:8501 | xargs kill -9
```

### Database connection error
```bash
# Start PostgreSQL
sudo systemctl start postgresql  # Linux
brew services start postgresql   # Mac
# or use Windows Services

# Check credentials in .env
psql -U postgres
```

### Missing dependencies
```bash
pip install --upgrade -r requirements.txt
```

## 🎓 Learn More

- **Backend**: `backend/main.py`
- **Frontend**: `streamlit_app.py`
- **ML Models**: `backend/ml_models.py`
- **Chatbot**: `backend/rag_chatbot.py`
- **Tests**: `test_complete.py`

---

That's it! You're ready to go. 🚀
