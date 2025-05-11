# discord_api.py
import requests
import json
import sys

class DiscordAPI:
    def __init__(self, token):
        self.token = token
        self.api_base = "https://discord.com/api/v10"
        self.headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json"
        }
        print(f"DiscordAPI inicializado com token: {token[:5]}...", file=sys.stderr)

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
            print(f"Mensagem enviada com sucesso para o canal {channel_id}", file=sys.stderr)
            return response.json()
        except Exception as e:
            print(f"Erro ao enviar mensagem: {str(e)}", file=sys.stderr)
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
            print(f"Obtidas {len(response.json())} mensagens do canal {channel_id}", file=sys.stderr)
            return response.json()
        except Exception as e:
            print(f"Erro ao obter mensagens: {str(e)}", file=sys.stderr)
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
            print(f"Obtidos {len(response.json())} canais do servidor {guild_id}", file=sys.stderr)
            return response.json()
        except Exception as e:
            print(f"Erro ao obter canais: {str(e)}", file=sys.stderr)
            return {"error": str(e)}
