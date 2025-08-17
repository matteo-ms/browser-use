# 🚂 Browser-Use Railway Deployment Guide

Guida completa per deployare browser-use su Railway con API funzionante e browser headless.

## 📋 Prerequisiti

- Account Railway (https://railway.app)
- Repository GitHub con browser-use
- File `.env` configurato con le API keys

## 🛠️ Configurazione Files

### 1. Dockerfile.railway

Il progetto include già un `Dockerfile.railway` ottimizzato per Railway con:

- ✅ **Browser headless**: Chromium installato via Playwright
- ✅ **Xvfb**: Virtual framebuffer per display headless
- ✅ **Configurazioni ottimizzate**: Flag Chrome per ambiente containerizzato
- ✅ **User non-root**: Sicurezza migliorata
- ✅ **Health check**: Monitoring automatico

### 2. railway.json

Configurazione Railway già pronta:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile.railway"
  },
  "deploy": {
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

## 🚀 Deploy Steps

### Passo 1: Preparazione Repository

1. **Fork/Clone** questo repository
2. **Assicurati** che questi file siano presenti:
   - `Dockerfile.railway`
   - `railway.json`
   - `browser_use/api/server.py`

### Passo 2: Deploy su Railway

1. **Login** su Railway: https://railway.app
2. **New Project** → **Deploy from GitHub repo**
3. **Seleziona** il tuo repository browser-use
4. **Railway** rileverà automaticamente `railway.json` e userà `Dockerfile.railway`

### Passo 3: Configurazione Environment Variables

Aggiungi queste variabili d'ambiente nel dashboard Railway:

#### **Obbligatorie:**
```bash
BROWSER_SERVICE_API_KEY=your-secret-api-key-here
OPENAI_API_KEY=sk-your-openai-key
# O in alternativa:
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
```

#### **Opzionali ma Raccomandati:**
```bash
# LLM Settings
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o-mini
MAX_TASK_STEPS=30
TASK_TIMEOUT=300

# Security
ALLOWED_ORIGINS=https://yourdomain.com

# Browser Settings
CHROME_PERSISTENT_SESSION=false
CHROME_HEADLESS=true
RESOLUTION=1920x1080x24

# Logging
BROWSER_USE_LOGGING_LEVEL=info
ANONYMIZED_TELEMETRY=false
```

### Passo 4: Deploy e Test

1. **Deploy automatico** inizierà dopo la configurazione
2. **Attendi** ~5-10 minuti per il primo deploy
3. **URL pubblico** sarà disponibile nel dashboard Railway

## 🧪 Testing del Deploy

### Health Check
```bash
curl https://your-app.railway.app/health
```

**Risposta attesa:**
```json
{
  "status": "ok",
  "message": "Browser-use API server attivo",
  "timestamp": "2025-01-17T18:00:00.000Z",
  "active_sessions": 0,
  "active_tasks": 0
}
```

### Test Task Execution
```bash
curl -X POST "https://your-app.railway.app/execute-task" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "task": "vai su google.com e cerca \"browser automation\"",
    "user_id": "test-user",
    "max_steps": 10
  }'
```

## 📊 Monitoraggio

### Logs Railway
```bash
railway logs --tail
```

### Metriche Disponibili
- **Health endpoint**: `/health`
- **Task status**: `/task-status/{task_id}`
- **User tasks**: `/user-tasks/{user_id}`

## ⚠️ Problemi Comuni e Soluzioni

### 1. Build Failure
**Problema**: Docker build fallisce
**Soluzione**: 
- Verifica che `Dockerfile.railway` sia presente
- Controlla i log di build in Railway

### 2. Browser CDP Error
**Problema**: "CDP client not initialized"
**Soluzione**: 
- Il browser headless è configurato ma potrebbe servire più memoria
- Aumenta la memoria del container in Railway (Settings → Resources)

### 3. API Key Error
**Problema**: "BROWSER_SERVICE_API_KEY must be set"
**Soluzione**:
- Aggiungi `BROWSER_SERVICE_API_KEY` nelle environment variables
- Usa una chiave sicura e unica

### 4. CORS Error
**Problema**: Errori CORS dal frontend
**Soluzione**:
- Aggiungi il tuo dominio in `ALLOWED_ORIGINS`
- Formato: `ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com`

## 🔧 Configurazioni Avanzate

### Scaling
```bash
# Railway CLI
railway up --replicas 3
```

### Custom Domain
1. **Settings** → **Domains** nel dashboard Railway
2. **Add Domain** → inserisci il tuo dominio
3. **Configura DNS** come indicato

### Database Integration
Per persistenza avanzata, puoi aggiungere:
- **PostgreSQL**: Per task history
- **Redis**: Per sessioni cache
- **S3**: Per file output

## 📈 Performance Tips

### Ottimizzazione Memory
```bash
# Environment variables
MAX_TASK_STEPS=20          # Riduci per task più leggeri
TASK_TIMEOUT=180           # Timeout più brevi
CHROME_PERSISTENT_SESSION=false  # Non mantenere sessioni
```

### Ottimizzazione Browser
```bash
# Già configurato in Dockerfile.railway
--disable-images           # No immagini
--disable-plugins          # No plugin
--disable-extensions       # No estensioni
```

## 🛡️ Security Best Practices

1. **API Key sicura**: Usa chiavi lunghe e casuali
2. **CORS configurato**: Solo domini autorizzati
3. **Rate limiting**: Implementa nel tuo frontend
4. **HTTPS only**: Railway fornisce SSL automatico
5. **Environment variables**: Mai committare chiavi nel codice

## 📚 API Endpoints

Documentazione completa disponibile in:
- `README_API.md`
- `/docs` endpoint (quando attivo)

### Endpoints Principali:
- `POST /execute-task` - Esegui task
- `GET /task-status/{task_id}` - Status task
- `GET /health` - Health check
- `GET /user-tasks/{user_id}` - Lista task utente

## 🎯 Conclusione

Con questa configurazione hai:
- ✅ **API browser-use** completamente funzionante
- ✅ **Browser headless** configurato per Railway
- ✅ **Scaling automatico** e monitoring
- ✅ **SSL/HTTPS** automatico
- ✅ **Deploy automatico** da GitHub

Il deploy è **pronto per produzione** e può gestire task di automazione browser in modo scalabile e affidabile!

---

**🚀 Happy deploying!**

Per supporto: [GitHub Issues](https://github.com/browser-use/browser-use/issues)
