# main.py
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import sys
import json

# Importar apenas a API do Discord
from discord_api import DiscordAPI

# Verificar token do Discord
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    print("ERRO: DISCORD_TOKEN não encontrado nas variáveis de ambiente!", file=sys.stderr)
    # Não encerraremos, pois o Render precisa que o servidor continue rodando

# Inicializar a API do Discord
discord_api = DiscordAPI(DISCORD_TOKEN)

# Criação da aplicação FastAPI
app = FastAPI(
    title="Discord MCP API",
    description="API para integração de Discord com MCP (Model Control Protocol)",
    version="1.0.0",
)

# O resto do código permanece igual...

# Modelos Pydantic para validação dos dados
class SendMessageRequest(BaseModel):
    channel_id: str
    message: str

class GetMessagesRequest(BaseModel):
    channel_id: str
    limit: Optional[int] = 10

class GetChannelsRequest(BaseModel):
    guild_id: str

class GenericResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

@app.get("/", tags=["Info"])
async def root():
    """Retorna informações básicas sobre a API."""
    return {
        "name": "Discord MCP API",
        "version": "1.0.0",
        "description": "API para integração de Discord com MCP"
    }

@app.post("/send-message", response_model=GenericResponse, tags=["Discord"])
async def send_message(request: SendMessageRequest):
    """
    Envia uma mensagem para um canal do Discord.
    
    - **channel_id**: ID do canal do Discord
    - **message**: Conteúdo da mensagem a ser enviada
    """
    try:
        result = discord_api.send_message(request.channel_id, request.message)
        if "error" in result:
            return {"success": False, "error": result["error"]}
        return {"success": True, "message": "Mensagem enviada com sucesso", "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/get-messages", tags=["Discord"])
async def get_messages(request: GetMessagesRequest):
    """
    Obtém mensagens recentes de um canal do Discord.
    
    - **channel_id**: ID do canal do Discord
    - **limit**: Número máximo de mensagens a serem retornadas (padrão: 10)
    """
    try:
        result = discord_api.get_channel_messages(request.channel_id, request.limit)
        if isinstance(result, dict) and "error" in result:
            return {"success": False, "error": result["error"]}
        
        # Simplificar as mensagens para retornar apenas os dados importantes
        simplified_messages = []
        for msg in result:
            simplified_messages.append({
                "id": msg.get("id"),
                "content": msg.get("content"),
                "author": {
                    "id": msg.get("author", {}).get("id"),
                    "username": msg.get("author", {}).get("username"),
                    "bot": msg.get("author", {}).get("bot", False)
                },
                "timestamp": msg.get("timestamp")
            })
        
        return {"success": True, "data": {"messages": simplified_messages}}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/get-channels", tags=["Discord"])
async def get_channels(request: GetChannelsRequest):
    """
    Obtém a lista de canais de um servidor do Discord.
    
    - **guild_id**: ID do servidor do Discord
    """
    try:
        result = discord_api.get_guild_channels(request.guild_id)
        if isinstance(result, dict) and "error" in result:
            return {"success": False, "error": result["error"]}
        
        # Simplificar os canais para retornar apenas os dados importantes
        simplified_channels = []
        for channel in result:
            simplified_channels.append({
                "id": channel.get("id"),
                "name": channel.get("name"),
                "type": channel.get("type"),
                "parent_id": channel.get("parent_id")
            })
        
        return {"success": True, "data": {"channels": simplified_channels}}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Rota para lidar com requisições MCP diretamente
@app.post("/mcp", tags=["MCP"])
async def handle_mcp(request: Request):
    """
    Manipula requisições no formato MCP (Model Control Protocol).
    
    Aceita comandos MCP para interagir com a API do Discord.
    """
    try:
        # Extrair o corpo da requisição
        body = await request.json()
        method = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id", "unknown")
        
        # Processar com base no método
        if method == "invoke":
            tool_method = params.get("method")
            arguments = params.get("arguments", {})
            
            if tool_method == "send_message":
                channel_id = arguments.get("channel_id")
                content = arguments.get("content")
                result = discord_api.send_message(channel_id, content)
                if "error" in result:
                    return {"success": False, "error": result["error"]}
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"success": True, "message": "Mensagem enviada com sucesso"}
                }
            
            elif tool_method == "get_messages":
                channel_id = arguments.get("channel_id")
                limit = arguments.get("limit", 10)
                result = discord_api.get_channel_messages(channel_id, limit)
                if isinstance(result, dict) and "error" in result:
                    return {"success": False, "error": result["error"]}
                
                # Simplificar as mensagens
                simplified_messages = []
                for msg in result:
                    simplified_messages.append({
                        "id": msg.get("id"),
                        "content": msg.get("content"),
                        "author": {
                            "username": msg.get("author", {}).get("username"),
                            "bot": msg.get("author", {}).get("bot", False)
                        },
                        "timestamp": msg.get("timestamp")
                    })
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"success": True, "messages": simplified_messages}
                }
            
            elif tool_method == "get_channels":
                guild_id = arguments.get("guild_id")
                result = discord_api.get_guild_channels(guild_id)
                if isinstance(result, dict) and "error" in result:
                    return {"success": False, "error": result["error"]}
                
                # Simplificar os canais
                simplified_channels = []
                for channel in result:
                    simplified_channels.append({
                        "id": channel.get("id"),
                        "name": channel.get("name"),
                        "type": channel.get("type")
                    })
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"success": True, "channels": simplified_channels}
                }
            
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Método não encontrado: {tool_method}"}
                }
        
        elif method == "initialize":
            # Retornar as capacidades do servidor
            capabilities = {
                "tools": {
                    "send_message": {
                        "description": "Envia uma mensagem para um canal do Discord",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "channel_id": {
                                    "type": "string",
                                    "description": "ID do canal do Discord"
                                },
                                "content": {
                                    "type": "string",
                                    "description": "Conteúdo da mensagem"
                                }
                            },
                            "required": ["channel_id", "content"]
                        }
                    },
                    "get_messages": {
                        "description": "Obtém mensagens recentes de um canal do Discord",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "channel_id": {
                                    "type": "string",
                                    "description": "ID do canal do Discord"
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "Número máximo de mensagens (padrão: 10)"
                                }
                            },
                            "required": ["channel_id"]
                        }
                    },
                    "get_channels": {
                        "description": "Obtém os canais de um servidor do Discord",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "guild_id": {
                                    "type": "string",
                                    "description": "ID do servidor do Discord"
                                }
                            },
                            "required": ["guild_id"]
                        }
                    }
                }
            }
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "serverInfo": {
                        "name": "Discord MCP API",
                        "version": "1.0.0"
                    },
                    "capabilities": capabilities
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Método MCP não encontrado: {method}"}
            }
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": "unknown",
                "error": {"code": -32603, "message": f"Erro interno: {str(e)}"}
            }
        )

if __name__ == "__main__":
    # Não é necessário incluir o código de inicialização do uvicorn aqui, 
    # pois o Render vai gerenciar isso
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
