# main.py
from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import sys
import json
import requests
import logging

# Configuração de logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Variáveis de ambiente
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DEFAULT_DISCORD_CHANNEL_ID = os.getenv("DEFAULT_DISCORD_CHANNEL_ID")

# Verificar token do Discord
if not DISCORD_TOKEN:
    logger.error("DISCORD_TOKEN não encontrado nas variáveis de ambiente!")
    # Não encerraremos, pois o Render precisa que o servidor continue rodando

# Implementação inline da API do Discord
class DiscordAPI:
    def __init__(self, token):
        self.token = token
        self.api_base = "https://discord.com/api/v10"
        self.headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json"
        }
        logger.info(f"DiscordAPI inicializado com token: {token[:5]}...")

    def send_message(self, channel_id, content):
        """
        Envia uma mensagem para um canal específico do Discord.
        
        Args:
            channel_id (str): ID do canal
            content (str): Conteúdo da mensagem
            
        Returns:
            dict: Resposta da API
        """
        url = f"{self.api_base}/channels/{channel_id}/messages"
        data = {
            "content": content
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            logger.info(f"Mensagem enviada com sucesso para o canal {channel_id}")
            return response.json()
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {str(e)}")
            return {"error": str(e)}
    
    def get_channel_messages(self, channel_id, limit=10):
        """
        Obtém as mensagens recentes de um canal.
        
        Args:
            channel_id (str): ID do canal
            limit (int): Número máximo de mensagens a obter
            
        Returns:
            list: Lista de mensagens
        """
        url = f"{self.api_base}/channels/{channel_id}/messages?limit={limit}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Obtidas {len(response.json())} mensagens do canal {channel_id}")
            return response.json()
        except Exception as e:
            logger.error(f"Erro ao obter mensagens: {str(e)}")
            return {"error": str(e)}
    
    def get_guild_channels(self, guild_id):
        """
        Obtém os canais de um servidor.
        
        Args:
            guild_id (str): ID do servidor
            
        Returns:
            list: Lista de canais
        """
        url = f"{self.api_base}/guilds/{guild_id}/channels"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Obtidos {len(response.json())} canais do servidor {guild_id}")
            return response.json()
        except Exception as e:
            logger.error(f"Erro ao obter canais: {str(e)}")
            return {"error": str(e)}

# Inicializar a API do Discord
discord_api = DiscordAPI(DISCORD_TOKEN)

# Criação da aplicação FastAPI
app = FastAPI(
    title="Discord MCP API",
    description="API para integração de Discord com MCP (Model Control Protocol) e GPT",
    version="1.0.0",
)

# Configuração de CORS para permitir requisições de diferentes origens
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permita todas as origens em ambiente de desenvolvimento
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    # Decide a URL base com base na variável de ambiente
    server_url = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:10000")
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Adicionar servidores de forma dinâmica
    openapi_schema["servers"] = [
        {"url": server_url, "description": "API Discord"}
    ]
    
    # Adicionar configurações específicas para o MCP
    openapi_schema["info"]["x-mcp-capabilities"] = {
        "tools": {
            "send_message": {
                "description": "Envia uma mensagem para um canal do Discord",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "ID do canal do Discord (opcional se canal padrão configurado)"
                        },
                        "content": {
                            "type": "string",
                            "description": "Conteúdo da mensagem"
                        }
                    },
                    "required": ["content"]
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
            }
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Modelos Pydantic para validação dos dados
class SendMessageRequest(BaseModel):
    channel_id: Optional[str] = None
    message: str

class QuickMessageRequest(BaseModel):
    message: str
    channel_id: Optional[str] = None  # Opcional, usa o padrão se não for fornecido

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
        "description": "API para integração de Discord com MCP e GPT",
        "default_channel_configured": bool(DEFAULT_DISCORD_CHANNEL_ID)
    }

@app.post("/send-message", response_model=GenericResponse, tags=["Discord"])
async def send_message(request: SendMessageRequest):
    """
    Envia uma mensagem para um canal específico do Discord.
    
    - **channel_id**: ID do canal do Discord (opcional se canal padrão configurado)
    - **message**: Conteúdo da mensagem a ser enviada
    """
    channel_id = request.channel_id or DEFAULT_DISCORD_CHANNEL_ID
    
    if not channel_id:
        logger.error("Canal não especificado e canal padrão não configurado")
        return {"success": False, "error": "Canal não especificado e canal padrão não configurado"}
    
    try:
        logger.info(f"Enviando mensagem para o canal {channel_id}")
        result = discord_api.send_message(channel_id, request.message)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Erro ao enviar mensagem: {result['error']}")
            return {"success": False, "error": result["error"]}
        return {
            "success": True, 
            "message": "Mensagem enviada com sucesso", 
            "data": result
        }
    except Exception as e:
        logger.exception("Exceção ao enviar mensagem")
        return {"success": False, "error": str(e)}

@app.post("/quick-message", response_model=GenericResponse, tags=["Discord"])
async def quick_message(request: QuickMessageRequest):
    """
    Envia uma mensagem rápida para o canal padrão ou para um canal específico.
    
    - **message**: Conteúdo da mensagem a ser enviada
    - **channel_id**: (Opcional) ID do canal do Discord. Se não fornecido, usa o canal padrão configurado
    """
    channel_id = request.channel_id or DEFAULT_DISCORD_CHANNEL_ID
    
    if not channel_id:
        logger.error("Canal não especificado e canal padrão não configurado")
        return {"success": False, "error": "Canal não especificado e canal padrão não configurado"}
    
    try:
        logger.info(f"Enviando mensagem rápida para o canal {channel_id}")
        result = discord_api.send_message(channel_id, request.message)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Erro ao enviar mensagem rápida: {result['error']}")
            return {"success": False, "error": result["error"]}
        return {
            "success": True, 
            "message": f"Mensagem enviada para o canal {channel_id}", 
            "data": result
        }
    except Exception as e:
        logger.exception("Exceção ao enviar mensagem rápida")
        return {"success": False, "error": str(e)}

@app.post("/get-messages", response_model=GenericResponse, tags=["Discord"])
async def get_messages(request: GetMessagesRequest):
    """
    Obtém mensagens recentes de um canal do Discord.
    
    - **channel_id**: ID do canal do Discord
    - **limit**: Número máximo de mensagens a serem retornadas (padrão: 10)
    """
    try:
        logger.info(f"Obtendo {request.limit} mensagens do canal {request.channel_id}")
        result = discord_api.get_channel_messages(request.channel_id, request.limit)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Erro ao obter mensagens: {result['error']}")
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
        
        return {
            "success": True, 
            "data": {"messages": simplified_messages, "count": len(simplified_messages)}
        }
    except Exception as e:
        logger.exception("Exceção ao obter mensagens")
        return {"success": False, "error": str(e)}

@app.get("/default-messages", response_model=GenericResponse, tags=["Discord"])
async def get_default_messages(limit: int = Query(10, description="Número máximo de mensagens")):
    """
    Obtém mensagens recentes do canal padrão configurado.
    
    - **limit**: Número máximo de mensagens a serem retornadas (padrão: 10)
    """
    if not DEFAULT_DISCORD_CHANNEL_ID:
        logger.error("Canal padrão não configurado")
        return {"success": False, "error": "Canal padrão não configurado"}
    
    try:
        logger.info(f"Obtendo {limit} mensagens do canal padrão {DEFAULT_DISCORD_CHANNEL_ID}")
        result = discord_api.get_channel_messages(DEFAULT_DISCORD_CHANNEL_ID, limit)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Erro ao obter mensagens do canal padrão: {result['error']}")
            return {"success": False, "error": result["error"]}
        
        # Simplificar as mensagens
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
        
        return {
            "success": True, 
            "data": {"messages": simplified_messages, "count": len(simplified_messages)}
        }
    except Exception as e:
        logger.exception("Exceção ao obter mensagens do canal padrão")
        return {"success": False, "error": str(e)}

@app.post("/get-channels", response_model=GenericResponse, tags=["Discord"])
async def get_channels(request: GetChannelsRequest):
    """
    Obtém a lista de canais de um servidor do Discord.
    
    - **guild_id**: ID do servidor do Discord
    """
    try:
        logger.info(f"Obtendo canais do servidor {request.guild_id}")
        result = discord_api.get_guild_channels(request.guild_id)
        if isinstance(result, dict) and "error" in result:
            logger.error(f"Erro ao obter canais: {result['error']}")
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
        
        return {
            "success": True, 
            "data": {"channels": simplified_channels, "count": len(simplified_channels)}
        }
    except Exception as e:
        logger.exception("Exceção ao obter canais")
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
        
        logger.info(f"Recebida requisição MCP: método={method}, id={request_id}")
        
        # Processar com base no método
        if method == "invoke":
            tool_method = params.get("method")
            arguments = params.get("arguments", {})
            
            if tool_method == "send_message":
                channel_id = arguments.get("channel_id") or DEFAULT_DISCORD_CHANNEL_ID
                if not channel_id:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32000, "message": "Canal não especificado e canal padrão não configurado"}
                    }
                
                content = arguments.get("content")
                result = discord_api.send_message(channel_id, content)
                if "error" in result:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32000, "message": result["error"]}
                    }
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
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32000, "message": result["error"]}
                    }
                
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
            
            else:
                logger.warning(f"Método MCP desconhecido: {tool_method}")
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
                                    "description": "ID do canal do Discord (opcional se canal padrão configurado)"
                                },
                                "content": {
                                    "type": "string",
                                    "description": "Conteúdo da mensagem"
                                }
                            },
                            "required": ["content"]
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
            logger.warning(f"Método MCP desconhecido: {method}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Método MCP não encontrado: {method}"}
            }
            
    except Exception as e:
        logger.exception(f"Exceção ao processar requisição MCP: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": "unknown",
                "error": {"code": -32603, "message": f"Erro interno: {str(e)}"}
            }
        )

# Rota adicional para compatibilidade com MCP
@app.get("/.well-known/openapi.json")
def mcp_openapi():
    """Rota para a especificação OpenAPI no formato exigido pelo MCP."""
    return get_custom_openapi()

# Sobrescreve a função openapi padrão do FastAPI
app.openapi = get_custom_openapi

if __name__ == "__main__":
    # Para execução local e testes
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    print(f"Iniciando servidor na porta {port}", file=sys.stderr)
    uvicorn.run(app, host="0.0.0.0", port=port)
