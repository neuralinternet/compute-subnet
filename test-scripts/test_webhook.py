from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()


@app.post("/api/gpus/webhook/deallocation")
async def webhook(request: Request):
    payload = await request.json()
    print("Received payload:", payload)
    # Do something with the payload if needed
    return JSONResponse(content={"status": "success", "message": "Webhook received"}, status_code=200)


@app.post("/api/gpus/webhook/status-change-warning")
async def webhook(request: Request):
    payload = await request.json()
    print("Received payload:", payload)
    # Do something with the payload if needed
    return JSONResponse(content={"status": "success", "message": "Webhook received"}, status_code=200)


if __name__ == "__main__":
    uvicorn.run(app,
                host="0.0.0.0",
                port=3000,
                log_level="info",
                ssl_certfile="cert/client.crt",
                ssl_keyfile="cert/client.key",
                ssl_ca_certs="cert/ca.cer", )
