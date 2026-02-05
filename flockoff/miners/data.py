from typing import Any, ClassVar, Dict, Optional, Type
from pydantic import BaseModel, Field, PositiveInt

# The maximum bytes for metadata on the chain.
MAX_METADATA_BYTES = 128
# The length, in bytes, of a git commit hash.
GIT_COMMIT_LENGTH = 40
# The length, in bytes, of a base64 encoded sha256 hash.
SHA256_BASE_64_LENGTH = 44
# The max length, in characters, of the competition id
MAX_COMPETITION_ID_LENGTH = 12


class ModelId(BaseModel):
    """Uniquely identifies a trained model"""

    MAX_REPO_ID_LENGTH: ClassVar[int] = (
        MAX_METADATA_BYTES
        - GIT_COMMIT_LENGTH
        - SHA256_BASE_64_LENGTH
        - MAX_COMPETITION_ID_LENGTH
        - 4  # separators
    )

    namespace: str = Field(
        description="Namespace where the dataset can be found. ex. Hugging Face username/org."
    )
    # Identifier for competition
    competition_id: Optional[str] = Field(description="The competition id")

    # When handling a model locally the commit and hash are not necessary.
    # Commit must be filled when trying to download from a remote store.
    commit: Optional[str] = Field(
        description="Commit of the model. May be empty if not yet committed."
    )

    def to_compressed_str(self) -> str:
        """Returns a compressed string representation."""
        return f"{self.namespace}:{self.competition_id}:{self.commit}"

    @classmethod
    def from_compressed_str(cls, cs: str) -> Type["ModelId"]:
        tokens = cs.split(":")
        return cls(
            namespace=tokens[0],
            competition_id=tokens[1],
            commit=tokens[2] if tokens[2] != "None" else "main",
        )


class ModelMetadata(BaseModel):
    id: ModelId = Field(description="Identifier for this trained model.")
    block: PositiveInt = Field(
        description="Block on which this model was claimed on the chain."
    )
