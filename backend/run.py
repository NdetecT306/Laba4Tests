#!/usr/bin/env python
import uvicorn
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
