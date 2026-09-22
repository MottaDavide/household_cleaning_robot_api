from pydantic import BaseModel

class CustomBase(BaseModel):
    """The base class every model in the service inherits from.

    Empty today. It exists so that settings shared by all the models have one
    obvious place to go later, instead of being repeated in each of them.
    """
    pass