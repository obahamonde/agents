import asyncio
from dataclasses import dataclass, field
from typing import Dict
from .faunadb import APIClient, APIConfig
from .openai import FunctionType

from ..config import env
from ..utils import nginx_render


@dataclass
class CloudFlare(APIClient):
    """Domain provisioning service"""

    base_url: str = field(default="https://api.cloudflare.com")
    headers: Dict[str, str] = field(
        default_factory=lambda: {
            "X-Auth-Email": env.CF_EMAIL,
            "X-Auth-Key": env.CF_API_KEY,
            "Content-Type": "application/json",
        }
    )

    async def provision(self, name: str, port: int):
        """
        Provision a new domain
        """
        try:
            response = await self.fetch(
                f"/client/v4/zones/{env.CF_ZONE_ID}/dns_records",
                "POST",
                json={
                    "type": "A",
                    "name": name,
                    "content": env.IP_ADDR,
                    "ttl": 1,
                    "priority": 10,
                    "proxied": True,
                },
            )
            assert isinstance(response, dict)
            data = response["result"]
            nginx_render(name=name, port=port)
            return {
                "url": f"https://{name}.aiofauna.com",
                "ip": f"https://{env.IP_ADDR}:{port}",
                "data": data,
            }
        except Exception as exc:
            raise exc

    async def delete_all(self):
        records = await self.fetch(
            f"/client/v4/zones/{env.CF_ZONE_ID}/dns_records",
        )

        results = records["result"]

        async def delete_record(record):
            await self.delete(f"/zones/{env.CF_ZONE_ID}/dns_records/{record['id']}")

        await asyncio.gather(*[delete_record(record) for record in results])

        return results


class DnsRecord(FunctionType):
    """
    This function creates a DNS Record in CloudFlare
    """
    host: str
    port: int

    async def run(self):
        return await CloudFlare().provision(self.host, self.port)
