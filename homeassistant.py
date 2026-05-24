import requests
import json
import websockets
import logging

logger = logging.getLogger(__name__)


class HomeAssistant:
    """Atualiza o Home Assistant via REST e websocket."""

    def __init__(self, ha_url: str, token: str, ha_ws_url: str):
        self.ha_url = ha_url
        self.token = token
        self.ha_ws_url = ha_ws_url

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def verificar_entidade(self, entity_id: str) -> dict:
        url = f"{self.ha_url}/api/states/{entity_id}"
        resp = requests.get(url, headers=self._headers(), timeout=10)

        if resp.status_code == 404:
            raise RuntimeError(
                f"A entidade '{entity_id}' não existe no Home Assistant. "
                f"Crie o helper input_number antes de rodar o script."
            )

        resp.raise_for_status()
        return resp.json()

    def atualizar_input_number(self, entity_id: str, valor: float) -> None:
        self.verificar_entidade(entity_id)

        url = f"{self.ha_url}/api/services/input_number/set_value"
        payload = {
            "entity_id": entity_id,
            "value": round(float(valor), 2),
        }

        resp = requests.post(url, headers=self._headers(),
                             json=payload, timeout=10)
        resp.raise_for_status()

        estado = self.verificar_entidade(entity_id)
        logger.info(f"{entity_id} atualizado para: {estado['state']}")

    async def importar_estatistica_mensal(
        self,
        statistic_id: str,
        name: str,
        unit: str,
        start_iso: str,
        value: float
    ) -> None:
        async with websockets.connect(self.ha_ws_url) as ws:
            msg = json.loads(await ws.recv())
            if msg.get("type") != "auth_required":
                raise RuntimeError(f"Websocket inesperado: {msg}")

            await ws.send(json.dumps({"type": "auth", "access_token": self.token}))
            auth_resp = json.loads(await ws.recv())
            if auth_resp.get("type") != "auth_ok":
                raise RuntimeError("Autenticação websocket falhou.")

            payload = {
                "id": 1,
                "type": "recorder/import_statistics",
                "metadata": {
                    "has_mean": True,
                    "has_sum": False,
                    "name": name,
                    "source": "recorder",
                    "statistic_id": statistic_id,
                    "unit_of_measurement": unit,
                },
                "stats": [
                    {
                        "start": start_iso,
                        "mean": float(value),
                        "min": float(value),
                        "max": float(value),
                    }
                ],
            }

            await ws.send(json.dumps(payload))
            resp = json.loads(await ws.recv())

            if not resp.get("success"):
                raise RuntimeError(f"Falha ao importar estatística: {resp}")

            logger.info(
                f"Estatística importada com sucesso para {statistic_id} em {start_iso}")