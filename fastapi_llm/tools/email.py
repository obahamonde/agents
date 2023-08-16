import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from ..service.faunadb import FaunaModel
from ..schema.typedefs import FunctionType
from boto3 import Session
from pydantic import EmailStr, Field

from ..config import AWSCredentials

credentials = AWSCredentials().dict()

aws = Session(**credentials)

ses = aws.client("ses")


class ContactForm(FunctionType, FaunaModel):
    """Fills a contact form for a user in order to suscribe to a newsletter,
    offers, premium content or custommer support. Must validate the email
    characters, verifies the email on SES and if it's not verified it will
    send a verification email"""

    name: str = Field(..., max_length=64)
    email: EmailStr = Field(...)
    message: Optional[str] = Field(default=None, max_length=512)
    verified: bool = Field(default=False)

    def send_email_ses(self):
        response = ses.send_email(
            Source="oscar.bahamonde.dev@gmail.com",
            Destination={"ToAddresses": [self.email]},
            Message={
                "Subject": {"Data": "Welcome to AioFauna"},
                "Body": {
                    "Text": {
                        "Data": f"Hello {self.name},\n\nThank you for contacting us. We will get back to you as soon as possible.\n\nBest regards,\nOscar Bahamonde",
                    }
                },
            },
        )
        return response

    async def run(self):
        identities = ses.list_identities()
        if self.email not in identities["Identities"]:
            ses.verify_email_identity(EmailAddress=self.email)
            self.verified = False
            await self.save()
        else:
            self.verified = True
            response = await asyncio.to_thread(self.send_email_ses)
            if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
                return await self.create()
            else:
                raise RuntimeError(response)
