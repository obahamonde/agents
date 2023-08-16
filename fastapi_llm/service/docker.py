from dataclasses import dataclass, field
from typing import *
from ..schema import Document
from .faunadb import APIClient, FaunaModel, Field

from ..utils import gen_port

TemplatesAvailable = Literal[
    "react", "vue", "python", "express", "fastapi", "php", "codeserver", "ruby"
]


class ContainerCreate(Document):
    login: str = Field(..., description="User reference")
    repo: str = Field(..., description="Repo reference")
    token: str = Field(..., description="Github token")
    email: str = Field(..., description="Email of the user")
    image: TemplatesAvailable = Field(..., description="Image to use")


class CodeServer(FaunaModel):
    user: str = Field(..., index=True, description="User reference")
    namespace: str = Field(..., description="User reference", unique=True)
    container_id: Optional[str] = Field(default=None)
    image: str = Field(default="codeserver", description="Image to use")
    host_port: int = Field(default_factory=gen_port, description="Port to expose")
    email: str = Field(..., description="Email of the user")
    env_vars: Optional[List[str]] = Field(
        default=[], description="Environment variables"
    )

    def payload(self, token: str, volume: str):
        extensions = [
            "ms-python.isort",
            "ms-python.python",
            "TabNine.tabnine-vscode",
            "PKief.material-icon-theme",
            "esbenp.prettier-vscode",
            "ms-python.isort",
            "ms-pyright.pyright",
            "RobbOwen.synthwave-vscode",
        ]
        assert isinstance(self.env_vars, list)
        self.env_vars.append(f"FAUNA_SECRET={token}")
        self.env_vars.append(f"EMAIL={self.email}")
        self.env_vars.append(f"PASSWORD={self.user}")
        self.env_vars.append("TZ=America/New_York")
        self.env_vars.append(f"USER={self.user}")
        self.env_vars.append(f"SUDO_PASSWORD={self.user}")
        self.env_vars.append(f"EXTENSIONS={','.join(extensions)}")
        git_startup_script = f"""
        set -e\n
        export HOME=/root\n
        export PATH=$PATH:/app/code-server/bin\n 
        """
        for extension in extensions:
            git_startup_script += f"code-server --install-extension {extension}\n"
        git_startup_script += """
        chmod -R 777 /config/workspace/\n
        code-server --disable-telemetry
        """

        return {
            "Image": self.image,
            "Env": self.env_vars,
            "ExposedPorts": {"8443/tcp": {"HostPort": str(self.host_port)}},
            "HostConfig": {
                "PortBindings": {"8443/tcp": [{"HostPort": str(self.host_port)}]},
                "Binds": [f"{volume}:/config/workspace"],
            },
            "Cmd": ["/usr/bin/bash", "-c", git_startup_script],
        }


class Runner(FaunaModel):
    user: Optional[str] = Field(default=None, index=True)
    namespace: str = Field(..., description="Github Repo", unique=True)
    image: str = Field(..., description="Image to use")
    host_port: int = Field(default_factory=gen_port, description="Port to expose")
    container_port: int = Field(default=8080, description="Port to expose")
    env_vars: List[str] = Field(
        default=["DOCKER=1"], description="Environment variables"
    )
    container_id: Optional[str] = Field(default=None)

    def payload(self, token: str, volume: str):
        assert isinstance(self.env_vars, list)
        if self.image == "php":
            dir_ = "/var/www/html"
        else:
            dir_ = "/app"
        return {
            "Image": self.image,
            "Env": self.env_vars + [f"FAUNA_SECRET={token}"],
            "ExposedPorts": {
                f"{self.container_port}/tcp": {"HostPort": str(self.host_port)}
            },
            "HostConfig": {
                "PortBindings": {
                    f"{self.container_port}/tcp": [{"HostPort": str(self.host_port)}]
                },
                "Binds": [f"{volume}:{dir_}"],
            },
        }


@dataclass
class DockerService(APIClient):
    """
    DockerService
        - start_container(container_id:str) -> None
        - create_volume(tag:str) -> str
        - create_container(body:ContainerCreate, volume:str) -> Container
    """

    async def start_container(self, container_id: str):
        """
        Starts a container
        - (container_id:str) -> None
        """
        await self.text(f"/containers/{container_id}/start", method="POST")

    async def create_volume(self, tag: str) -> str:
        """Create a volume
        - (tag:str) -> str
        """
        payload = {"Name": tag, "Driver": "local"}
        await self.fetch(
            "/volumes/create",
            method="POST",
            json=payload,
        )
        return tag

    async def create_container(self, body: ContainerCreate, volume: str, token: str):
        """Create a python container
        - (body:ContainerCreate) -> Container
        """
        container = Runner(**body.dict())
        payload = container.payload(token, volume)
        response = await self.fetch(
            "/containers/create",
            method="POST",
            json=payload,
        )
        assert isinstance(response, dict)

        container.container_id = response["Id"]
        instance = await container.save()
        assert isinstance(instance, Runner)
        assert isinstance(instance.container_id, str)
        await self.start_container(instance.container_id)
        return instance

    async def create_code_server(
        self, body: ContainerCreate, volume: str, token: str
    ) -> CodeServer:
        """
        Create a code-server container
        - (body:ContainerCreate) -> CodeServer
        """
        codeserver = CodeServer(**body.dict())
        payload = codeserver.payload(token, volume)
        response = await self.fetch(
            "/containers/create",
            method="POST",
            json=payload,
        )
        assert isinstance(response, dict)
        codeserver.container_id = response["Id"]
        instance = await codeserver.save()
        assert isinstance(instance, CodeServer)
        assert isinstance(instance.container_id, str)
        await self.start_container(instance.container_id)
        return instance
