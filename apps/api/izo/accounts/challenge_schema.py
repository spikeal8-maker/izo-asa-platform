"""AUTH-002 input/output contracts; never echo passwords or proof tokens."""
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from .schemas import StrictInput, RegisterInput, normalize_email


class EmailRequest(StrictInput):
    email: str = Field(max_length=254)
    _email = field_validator("email")(normalize_email)


class ProofInput(StrictInput):
    token: SecretStr = Field(min_length=76, max_length=76)


class NewPassword(StrictInput):
    password: SecretStr = Field(min_length=15, max_length=128)
    confirmation: SecretStr = Field(min_length=15, max_length=128)

    @field_validator("password", "confirmation")
    @classmethod
    def valid_password(cls, value: SecretStr) -> SecretStr:
        return RegisterInput.password_policy(value)

    @model_validator(mode="after")
    def matching(self):
        if self.password.get_secret_value() != self.confirmation.get_secret_value():
            raise ValueError("Passwords must match")
        return self


class ResetInput(NewPassword, ProofInput):
    pass


class ChangePasswordInput(NewPassword):
    current_password: SecretStr = Field(min_length=1, max_length=128)


class MailReceipt(BaseModel):
    accepted: bool = True
    delivery: str = "test"


class EmptyInput(StrictInput):
    pass
