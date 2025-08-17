# Browser-Use Multi-User API

API REST completa per automazione browser multi-utente basata su browser-use.

## 🚀 Caratteristiche

- **Multi-Utente**: Isolamento completo tra utenti con sessioni browser persistenti
- **Task Generici**: Esegue qualsiasi task descrittivo (non solo LinkedIn)
- **Monitoring Real-Time**: Tracking status task con rilevamento stalli
- **File Output**: Gestione automatica GIF, screenshots, history JSON
- **Sicurezza**: Autenticazione API key, CORS configurabile
- **Scalabilità**: Deploy Docker con volumi persistenti

## 📋 Architettura

```
TUA WEBAPP → Browser-Use API → Sessioni Browser Isolate
                            ├── User1: Browser Session
                            ├── User2: Browser Session  
                            └── UserN: Browser Session
```

## 🛠️ Setup Rapido

### 1. Configurazione Environment

```bash
# Copia template configurazione
cp .env.example.api .env

# Modifica con i tuoi valori
nano .env
```

Configura almeno:
- `BROWSER_SERVICE_API_KEY`: La tua API key segreta
- `OPENAI_API_KEY`: Per GPT models
- `ALLOWED_ORIGINS`: Domini autorizzati

### 2. Deploy con Docker

```bash
# Build e avvio
docker-compose up -d

# Verifica status
docker-compose logs -f browser-use-api
```

### 3. Test API

```bash
# Installa dipendenze test
pip install httpx

# Esegui test completo
python scripts/test_api.py --url http://localhost:8000 --api-key your-api-key
```

## 📡 Endpoints API

### Esecuzione Task

```bash
POST /execute-task
Content-Type: application/json
X-API-Key: your-api-key

{
  "task": "vai su google.com e cerca 'python automation'",
  "user_id": "user123",
  "max_steps": 20
}
```

**Risposta:**
```json
{
  "success": true,
  "task_id": "task-1704123456789-abc123",
  "user_id": "user123",
  "session_id": "session-user123-1704123456",
  "message": "Task in coda per utente user123"
}
```

### Status Task

```bash
GET /task-status/{task_id}
X-API-Key: your-api-key
```

**Risposta:**
```json
{
  "task_id": "task-1704123456789-abc123",
  "user_id": "user123", 
  "status": "completed",
  "steps_completed": 15,
  "created_at": "2024-01-01T12:00:00Z",
  "completed_at": "2024-01-01T12:02:30Z",
  "has_files": true,
  "history_url": "http://localhost:8000/files/task-123/task-123.json",
  "gif_url": "http://localhost:8000/files/task-123/task-123.gif"
}
```

### Altri Endpoints

- `GET /health` - Health check
- `POST /task-cancel/{task_id}` - Cancella task
- `GET /user-tasks/{user_id}` - Lista task utente
- `DELETE /user-session/{user_id}` - Pulisci sessione utente

## 💡 Esempi di Utilizzo

### Task Generici

```python
import httpx

async def execute_browser_task(user_id: str, task: str):
    async with httpx.AsyncClient() as client:
        # Esegui task
        response = await client.post(
            "http://localhost:8000/execute-task",
            json={
                "task": task,
                "user_id": user_id,
                "max_steps": 30
            },
            headers={"X-API-Key": "your-api-key"}
        )
        
        result = response.json()
        task_id = result["task_id"]
        
        # Monitora completamento
        while True:
            status_response = await client.get(
                f"http://localhost:8000/task-status/{task_id}",
                headers={"X-API-Key": "your-api-key"}
            )
            
            status = status_response.json()
            
            if status["status"] in ["completed", "error"]:
                return status
            
            await asyncio.sleep(5)

# Esempi di task
await execute_browser_task("user1", "vai su amazon.com e cerca 'laptop gaming'")
await execute_browser_task("user2", "compila il form su httpbin.org/forms/post")
await execute_browser_task("user3", "vai su github.com e trova i repository più popolari per 'ai'")
```

### Integrazione con tua WebApp

```javascript
// Frontend JavaScript
async function runBrowserTask(userId, taskDescription) {
    // Avvia task
    const response = await fetch('/api/browser-task', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer your-jwt-token'
        },
        body: JSON.stringify({
            user_id: userId,
            task: taskDescription
        })
    });
    
    const { task_id } = await response.json();
    
    // Monitora progresso
    return new Promise((resolve) => {
        const checkStatus = async () => {
            const statusResponse = await fetch(`/api/browser-task/${task_id}/status`);
            const status = await statusResponse.json();
            
            if (status.status === 'completed') {
                resolve(status);
            } else if (status.status === 'error') {
                reject(new Error(status.error_message));
            } else {
                setTimeout(checkStatus, 2000);
            }
        };
        
        checkStatus();
    });
}
```

```python
# Backend Python (FastAPI/Django)
@app.post("/api/browser-task")
async def create_browser_task(request: TaskRequest, user: User = Depends(get_current_user)):
    # Chiama browser-use API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BROWSER_USE_API_URL}/execute-task",
            json={
                "task": request.task,
                "user_id": str(user.id),
                "max_steps": 30
            },
            headers={"X-API-Key": BROWSER_USE_API_KEY}
        )
        
        return response.json()
```

## 🔧 Configurazione Avanzata

### Personalizzazione Browser

```yaml
# docker-compose.yml
environment:
  - CHROME_PERSISTENT_SESSION=true  # Mantieni sessioni
  - RESOLUTION=1920x1080x24         # Risoluzione display
  - MAX_TASK_STEPS=50               # Max step per task
  - TASK_TIMEOUT=600                # Timeout task (secondi)
```

### Monitoring e Logging

```bash
# Logs real-time
docker-compose logs -f browser-use-api

# Metriche sistema
curl -H "X-API-Key: your-key" http://localhost:8000/health
```

### Storage e Cleanup

```bash
# Verifica utilizzo storage
du -sh ./data/

# Cleanup manuale task vecchi
docker-compose exec browser-use-api python -c "
from browser_use.api.file_manager import get_file_manager
fm = get_file_manager()
result = fm.cleanup_old_tasks(max_age_days=3)
print(f'Cleaned {result[\"cleaned_count\"]} tasks')
"
```

## 🚨 Sicurezza

### API Key

- Usa sempre API key forti e uniche
- Ruota le chiavi regolarmente
- Non esporre mai le chiavi nel frontend

### CORS

```bash
# Configura domini autorizzati
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

### Isolamento Utenti

- Ogni utente ha directory dati separata
- Sessioni browser completamente isolate
- Nessuna condivisione dati tra utenti

## 🔍 Troubleshooting

### Task Bloccati

```bash
# Verifica task attivi
curl -H "X-API-Key: your-key" http://localhost:8000/user-tasks/user123

# Cancella task bloccato
curl -X POST -H "X-API-Key: your-key" http://localhost:8000/task-cancel/task-id
```

### Problemi Browser

```bash
# Restart servizio
docker-compose restart browser-use-api

# Pulisci sessione utente
curl -X DELETE -H "X-API-Key: your-key" http://localhost:8000/user-session/user123
```

### Performance

- Limita task concorrenti per utente
- Configura cleanup automatico
- Monitora utilizzo memoria/CPU

## 📈 Scalabilità

### Load Balancing

```yaml
# docker-compose.yml
services:
  browser-use-api:
    deploy:
      replicas: 3
```

### Storage Condiviso

```yaml
volumes:
  browser_use_data:
    driver: nfs
    driver_opts:
      share: your-nfs-server:/data
```

## 🤝 Supporto

- **Issues**: GitHub Issues per bug e feature request
- **Docs**: Documentazione completa browser-use
- **Community**: Discord browser-use

---

**🎯 La tua piattaforma multi-utente è pronta!**

Con questa implementazione hai un servizio browser-use completamente isolato per utente, scalabile e pronto per produzione. Ogni utente può eseguire task generici mantenendo le proprie sessioni browser persistenti.
