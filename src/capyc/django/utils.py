from typing import Any, Callable, Optional, Type

from django.db import models

type QueryHandlerFn = Callable[[str, Optional[list[str]]], Any]
type QueryHandler = tuple[QueryHandlerFn, QueryHandlerFn | None, list[str]]


class FieldRelatedDescriptor:

    def __init__(
        self,
        path: str,
        field_name: str,
        field_alias: str,
        nullable: bool,
        related_model: models.Model,
        query_handler: Optional[QueryHandler] = None,
        blank: bool = False,
        default: Any = None,
        help_text: str = "",
        editable: bool = True,
        is_relation: bool = False,
        primary_key: bool = False,
        unique: bool = False,
        query_param: Optional[str] = None,
    ):
        self.path = path
        self.field_name = field_name
        self.field_alias = field_alias
        self.nullable = nullable
        self.related_model = related_model
        self.query_handler = query_handler
        self.blank = blank
        self.default = default
        self.help_text = help_text
        self.editable = editable
        self.is_relation = is_relation
        self.primary_key = primary_key
        self.unique = unique
        self.query_param = query_param

    def __repr__(self) -> str:
        return (
            f'<Descriptor path="{self.path}", field_name="{self.field_name}", '
            f'field_alias="{self.field_alias}", nullable={self.nullable}, related_model={self.related_model}>'
        )


class Choice:
    display_name: Any
    value: Any

    def __init__(self, display_name: Any, value: Any):
        self.display_name = display_name
        self.value = value


class FieldDescriptor:
    def __init__(
        self,
        type: Type[models.Field],
        primary_key: bool,
        max_length: int,
        field_name,
        is_relation: int,
        editable: bool,
        help_text: str,
        null: bool,
        blank: bool,
        choices: list[Choice],
        # related_model: models.Model,
        serializer: Optional[callable] = None,
        query_handler: Optional[QueryHandler] = None,
        default: Any = None,
        unique: bool = False,
    ):
        self.type = type
        self.primary_key = primary_key
        self.max_length = max_length
        self.field_name = field_name
        self.is_relation = is_relation
        self.editable = editable
        self.help_text = help_text
        # self.auto_created = auto_created
        # self.field_alias = field_alias
        self.null = null
        self.blank = blank
        self.choices = choices
        # self.related_model = related_model
        self.serializer = serializer
        self.query_handler = query_handler
        self.default = default
        self.unique = unique

    def __repr__(self) -> str:
        return (
            f"<FieldDescriptor type={self.type}, primary_key={self.primary_key}, max_length={self.max_length}, "
            f'field_name="{self.field_name}", is_relation={self.is_relation}, editable={self.editable}, '
            f'help_text="{self.help_text}", null={self.null}, blank={self.blank}, choices={self.choices}>'
        )


class ModelCache:

    def __init__(self):
        self.reverse_one_to_one_list: list[FieldRelatedDescriptor] = []
        self.reverse_many_to_one_list: list[FieldRelatedDescriptor] = []
        self.forward_one_to_one_list: list[FieldRelatedDescriptor] = []
        self.forward_many_to_one_list: list[FieldRelatedDescriptor] = []
        self.many_to_many_list: list[FieldRelatedDescriptor] = []
        self.id_list: list[FieldDescriptor] = []
        self.field_list: list[FieldDescriptor] = []
        self.lookup_rewrites: dict[str, str] = {}
        self.query_params: dict[str, str] = {}
