from io import BytesIO
from typing import List, Literal, Optional
from ..utils import async_io
from boto3 import Session
from pydantic import BaseModel, Field

LanguageCodeType = Literal[
    "arb",
    "cmn-CN",
    "cy-GB",
    "da-DK",
    "de-DE",
    "en-AU",
    "en-GB",
    "en-GB-WLS",
    "en-IN",
    "en-US",
    "es-ES",
    "es-MX",
    "es-US",
    "fr-CA",
    "fr-FR",
    "is-IS",
    "it-IT",
    "ja-JP",
    "hi-IN",
    "ko-KR",
    "nb-NO",
    "nl-NL",
    "pl-PL",
    "pt-BR",
    "pt-PT",
    "ro-RO",
    "ru-RU",
    "sv-SE",
    "tr-TR",
    "en-NZ",
    "en-ZA",
    "ca-ES",
    "de-AT",
    "yue-CN",
    "ar-AE",
    "fi-FI",
    "en-IE",
    "nl-BE",
]


class Polly(BaseModel):
    Engine: Literal["standard", "neural"] = Field(
        default="standard",
        description="Specifies the engine for Amazon Polly to use when processing input text for speech synthesis.",
    )
    LanguageCode: LanguageCodeType = Field(
        default="en-US",
        description="Optional language code for the Synthesize Speech request.",
    )
    LexiconNames: Optional[List[str]] = Field(
        default=None,
        description="List of one or more pronunciation lexicon names you want the service to apply during synthesis.",
    )
    OutputFormat: Literal["json", "mp3", "ogg_vorbis", "pcm"] = Field(
        default="mp3",
        description="The format in which the returned output will be encoded.",
    )
    SampleRate: str = Field(
        default="22050", description="The audio frequency specified in Hz."
    )
    SpeechMarkTypes: Optional[
        List[Literal["sentence", "ssml", "viseme", "word"]]
    ] = Field(
        default=None,
        description="The type of speech marks returned for the input text.",
    )
    Text: str = Field(..., description="Input text to synthesize.")
    TextType: Literal["ssml", "text"] = Field(
        default="text",
        description="Specifies whether the input text is plain text or SSML.",
    )
    VoiceId: str = Field(
        default="Mia", description="Voice ID to use for the synthesis."
    )

    @classmethod
    def from_text(cls, text: str):
        return cls(Text=text)

    @property
    def client(self):
        return Session().client("polly", region_name="us-east-1")

    def synthesize(self):
        return self.client.synthesize_speech(**self.dict(exclude_none=True))

    @async_io
    def get_audio(self):
        byte_stream = BytesIO()
        with self.synthesize()["AudioStream"] as stream:
            byte_stream.write(stream.read())
        byte_stream.seek(0)
        return byte_stream
