import base64
import json
import math
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Collection, Iterable, List, Optional, Type, TypedDict
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from adrf.requests import AsyncRequest
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import models
from django.db.models import (
    AutoField,
    BigAutoField,
    BigIntegerField,
    BinaryField,
    BooleanField,
    CharField,
    CommaSeparatedIntegerField,
    Count,
    DateField,
    DateTimeField,
    DecimalField,
    DurationField,
    EmailField,
    FileField,
    FilePathField,
    FloatField,
    GenericIPAddressField,
    ImageField,
    IntegerField,
    IPAddressField,
    PositiveBigIntegerField,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    Q,
    QuerySet,
    SlugField,
    SmallAutoField,
    SmallIntegerField,
    TextField,
    TimeField,
    URLField,
    UUIDField,
)
from django.db.models import fields as django_fields
from django.db.models.fields.related_descriptors import (
    ForeignKeyDeferredAttribute,
    ForwardManyToOneDescriptor,
    ForwardOneToOneDescriptor,
    ManyToManyDescriptor,
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
)
from django.db.models.query_utils import DeferredAttribute
from django.http import HttpRequest, HttpResponse

from capyc.django.cache import get_cache, set_cache
from capyc.django.utils import (
    Choice,
    FieldDescriptor,
    FieldRelatedDescriptor,
    ModelCache,
    QueryHandler,
)
from capyc.rest_framework.exceptions import ValidationException

__all__ = ["Serializer"]


def update_querystring(url, params):
    url_parts = list(urlparse(url))
    query = dict(parse_qs(url_parts[4]))
    query.update(params)
    url_parts[4] = urlencode(query, doseq=True)
    return urlunparse(url_parts)


CAPYC = getattr(settings, "CAPYC", {})
if "pagination" in CAPYC and isinstance(CAPYC["pagination"], dict):
    pks_limit = CAPYC["pagination"].get("pks", 200)
    page_limit = CAPYC["pagination"].get("pages", 20)

    PKS_LIMIT = pks_limit if pks_limit <= 1000 else 1000
    PAGE_LIMIT = page_limit if page_limit <= 100 else 100

else:
    PKS_LIMIT = 200
    PAGE_LIMIT = 20


def pk_serializer(field: Any) -> Any:
    return field.pk if field else None


def binary_serializer(field: bytes) -> str:
    return base64.b64encode(field).decode("utf-8")


def comma_separated_integer_serializer(field: str) -> list[int]:
    return [int(x) for x in field.split(",") if x]


def time_serializer(field: datetime) -> str:
    return field.isoformat().replace("+00:00", "Z")


def duration_serializer(field: timedelta) -> str:
    total_seconds = int(field.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


CUSTOM_SERIALIZERS = {
    BinaryField: binary_serializer,
    CommaSeparatedIntegerField: comma_separated_integer_serializer,
    DateTimeField: time_serializer,
    TimeField: time_serializer,
    DurationField: duration_serializer,
}

TRUE_VALUES = ["true", "1", "yes", "on", "True", "TRUE", "true", "Y", "Yes", "YES", "On", "ON"]
FALSE_VALUES = ["false", "0", "no", "off", "False", "FALSE", "false", "N", "No", "NO", "Off", "OFF"]


def binary_query(value: str, lookups: Optional[list[str]] = None) -> str:
    return base64.b64decode(value)


def binary_error_handler(key: str, lookups: Optional[list[str]] = None) -> str:
    return f"Invalid value for `{key}`, expected a base64 encoded binary field"


def decimal_query(value: str, lookups: Optional[list[str]] = None) -> str:
    return Decimal(value)


def decimal_error_handler(key: str, lookups: Optional[list[str]] = None) -> str:
    return f"Invalid value for `{key}`, expected a decimal number"


def float_query(value: str, lookups: Optional[list[str]] = None) -> str:
    return float(value)


def float_error_handler(key: str, lookups: Optional[list[str]] = None) -> str:
    return f"Invalid value for `{key}`, expected a float number"


def int_query(value: str, lookups: Optional[list[str]] = None) -> str:
    return int(value)


def int_error_handler(key: str, lookups: Optional[list[str]] = None) -> str:
    return f"Invalid value for `{key}`, expected an integer"


def bool_query(value: str, lookups: Optional[list[str]] = None) -> str:
    if value in TRUE_VALUES:
        return True

    elif value in FALSE_VALUES:
        return False

    return None


def bool_error_handler(key: str, lookups: Optional[list[str]] = None) -> str:
    return f"Invalid value for `{key}`, expected a boolean"


GENERAL_LOOKUP = ["exact", "in", "isnull"]
STRING_LOOKUP = [
    *GENERAL_LOOKUP,
    "iexact",
    "contains",
    "icontains",
    "in",
    "startswith",
    "istartswith",
    "endswith",
    "iendswith",
    "regex",
    "iregex",
]
NUMBER_LOOKUP = [*GENERAL_LOOKUP, "gt", "gte", "lt", "lte", "range"]
DATE_LOOKUP = [*NUMBER_LOOKUP, "year", "month", "day", "week_day"]
DATETIME_LOOKUP = [*DATE_LOOKUP, "year", "month", "day", "week_day", "hour", "minute", "second"]
TIME_LOOKUP = [*NUMBER_LOOKUP, "hour", "minute", "second"]
# JSON_LOOKUP = ["contained_by", "has_key", 'has_any_keys']


def datetime_query(value: str, lookups: Optional[list[str]] = None) -> str:
    if lookups and any(x in lookups for x in ["year", "month", "day", "week_day", "hour", "minute", "second"]):
        return int_query(value)

    return datetime.fromisoformat(value)


def datetime_error_handler(key: str, lookups: Optional[list[str]] = None) -> str:
    if lookups and any(x in lookups for x in ["year", "month", "day", "week_day", "hour", "minute", "second"]):
        return int_error_handler(key)

    return f"Invalid value for `{key}`, expected a datetime string"


def str_query(value: str, lookups: Optional[list[str]] = None) -> str:
    return value


def time_query(value: str, lookups: Optional[list[str]] = None) -> str:
    return value


QUERY_REWRITES = {
    BinaryField: (binary_query, None, GENERAL_LOOKUP),
    DecimalField: (decimal_query, decimal_error_handler, NUMBER_LOOKUP),
    FloatField: (float_query, float_error_handler, NUMBER_LOOKUP),
    IntegerField: (int_query, int_error_handler, NUMBER_LOOKUP),
    BooleanField: (bool_query, None, GENERAL_LOOKUP),
    DateTimeField: (datetime_query, datetime_error_handler, DATETIME_LOOKUP),
    DateField: (datetime_query, datetime_error_handler, DATE_LOOKUP),
    CharField: (str_query, None, STRING_LOOKUP),
    FileField: (str_query, None, STRING_LOOKUP),
    ImageField: (str_query, None, STRING_LOOKUP),
    FilePathField: (str_query, None, STRING_LOOKUP),
    IPAddressField: (str_query, None, STRING_LOOKUP),
    GenericIPAddressField: (str_query, None, STRING_LOOKUP),
    TextField: (str_query, None, STRING_LOOKUP),
    SlugField: (str_query, None, STRING_LOOKUP),
    UUIDField: (str_query, None, STRING_LOOKUP),
    DurationField: (str_query, None, NUMBER_LOOKUP),
    EmailField: (str_query, None, STRING_LOOKUP),
    BigIntegerField: (int_query, int_error_handler, NUMBER_LOOKUP),
    SmallIntegerField: (int_query, int_error_handler, NUMBER_LOOKUP),
    PositiveBigIntegerField: (int_query, int_error_handler, NUMBER_LOOKUP),
    PositiveIntegerField: (int_query, int_error_handler, NUMBER_LOOKUP),
    PositiveSmallIntegerField: (int_query, int_error_handler, NUMBER_LOOKUP),
    TimeField: (time_query, None, TIME_LOOKUP),
    URLField: (str_query, None, STRING_LOOKUP),
    AutoField: (int_query, int_error_handler, NUMBER_LOOKUP),
    BigAutoField: (int_query, int_error_handler, NUMBER_LOOKUP),
    SmallAutoField: (int_query, int_error_handler, NUMBER_LOOKUP),
}


class FilterOperation(TypedDict):
    parents: list[str]
    field: str
    operation: str
    value: Any


MODEL_CACHE: dict[str, ModelCache] = {}
MODEL_REL_CACHE: dict[str, dict[str, FieldRelatedDescriptor]] = {}
SERIALIZER_PARENTS: dict[str, set[str]] = {}
SERIALIZER_DEPTHS: dict[str, int] = {}
SERIALIZER_REGISTRY: dict[str, set[str]] = {}


class ExpandSets(TypedDict):
    sets: set[str]
    forward: set[str]
    parents: set[str]


class SerializerMetaBuilder:
    depth = 1
    request: Optional[HttpRequest | AsyncRequest] = None
    path: Optional[str] = None
    model: Optional[models.Model] = None
    lock = False
    fields = {"default": tuple()}
    rewrites = {}
    _children_sets: dict[str, ExpandSets] = {}
    _related_serializers: dict[str, Type["Serializer"]] = {}

    @classmethod
    def _get_expand_sets(cls, key: str) -> tuple[str, set[str]]:
        result = re.search(r"(.+)\[(.*?)\]", key)
        if not result:
            return key, set()

        g1 = result.group(1)
        g2 = result.group(2)

        if g2 == "":
            return g1, set()

        return g1, set(g2.split(","))

    @classmethod
    def get_model_path(cls, model: Optional[models.Model] = None):
        if model is None:
            model = cls.model

        return f"{model._meta.app_label}.{model.__name__}"

    @classmethod
    def get_serializer_path(cls, serializer: Optional[Type["Serializer"]] = None):
        if serializer is None:
            serializer = cls

        return f"{serializer.__module__}.{serializer.__name__}"

    @classmethod
    def _populate_parents(cls, cache: ModelCache):
        # cache.field_list = list(set(cache.field_list))
        # cache.id_list = list(set(cache.id_list))

        l = (
            cache.many_to_many_list
            + cache.reverse_many_to_one_list
            + cache.reverse_one_to_one_list
            + cache.forward_many_to_one_list
            + cache.forward_one_to_one_list
        )

        current = cls.get_serializer_path()
        model = cls.get_model_path()
        if model not in SERIALIZER_REGISTRY:
            SERIALIZER_REGISTRY[model] = set()

        SERIALIZER_REGISTRY[model].add(current)

        for descriptor in l:
            field_name = cls.rewrites.get(descriptor.field_name, descriptor.field_name)
            serializer = getattr(cls, field_name, None)
            if serializer is None:
                continue

            key = cls.get_serializer_path(serializer)
            if key not in SERIALIZER_PARENTS:
                SERIALIZER_PARENTS[key] = set()

            SERIALIZER_PARENTS[key].add(current)

    @classmethod
    def _get_related_fields(cls):
        model = cls.model
        key = model._meta.app_label + "." + model.__name__
        cache = MODEL_CACHE.get(key)
        if cache is None:
            cache = ModelCache()
            MODEL_CACHE[key] = cache

        cls.cache = MODEL_CACHE[key]

        rel_cache = MODEL_REL_CACHE.get(key)
        if rel_cache:
            cls.rel = rel_cache
            return

        # if rel_cache is None:
        rel_cache = {}
        MODEL_REL_CACHE[key] = rel_cache
        cls.rel = rel_cache

        def get_related_attrs(field, name):
            x = field
            if hasattr(field, "field"):
                field = field.field

                if hasattr(field, "m2m_field_name"):
                    cls.cache.lookup_rewrites[name] = field.m2m_field_name()

            else:
                field = field.related

            if hasattr(field, "attname"):
                queryattr = field.attname
            else:
                queryattr = field.accessor_name

            blank = False
            if hasattr(field, "blank"):
                blank = field.blank

            default = None
            if hasattr(field, "default"):
                default = field.default

            help_text = ""
            if hasattr(field, "help_text"):
                help_text = field.help_text

            primary_key = False
            if hasattr(field, "primary_key"):
                primary_key = field.primary_key

            unique = False
            if hasattr(field, "unique"):
                unique = field.unique

            if queryattr.endswith("_id"):
                queryattr = queryattr[:-3]

            elif queryattr.endswith("_set"):
                queryattr = queryattr[:-4]

            elif queryattr.endswith("_pk"):
                queryattr = queryattr[:-3]

            related_model = field.related_model
            path = field.related_model._meta.app_label + "." + field.related_model.__name__
            if hasattr(x, "rel") and hasattr(x, "reverse"):
                if x.reverse:
                    path = x.rel.related_model._meta.app_label + "." + x.rel.related_model.__name__
                    related_model = x.rel.related_model

            cls.cache.query_params[name] = queryattr

            obj = FieldRelatedDescriptor(
                path=path,
                field_name=name,
                field_alias=field.name,
                nullable=field.null,
                related_model=related_model,
                query_handler=QUERY_REWRITES.get(type(field), None),
                blank=blank,
                default=default,
                help_text=help_text,
                editable=field.editable,
                is_relation=field.is_relation,
                primary_key=primary_key,
                unique=unique,
                query_param=queryattr,
            )

            return obj

        def get_attrs(field, name):
            field = field.field
            if x := getattr(field, "_choices", None):
                choices = [Choice(display_name=display_name, value=value) for display_name, value in x]
            else:
                choices = None

            serializer = CUSTOM_SERIALIZERS.get(type(field), None)

            obj = FieldDescriptor(
                primary_key=field.primary_key,
                type=type(field),
                max_length=field.max_length,
                field_name=name,
                is_relation=field.is_relation,
                editable=field.editable,
                help_text=field.help_text,
                null=field.null,
                blank=field.blank,
                choices=choices,
                serializer=serializer,
                query_handler=QUERY_REWRITES.get(type(field), None),
                default=field.default,
                unique=field.unique,
            )

            return obj

        def set_field_descriptors(descriptor_list: list[FieldDescriptor], x: str):
            descriptor = get_attrs(getattr(model, x), x)
            descriptor_list.append(descriptor)

        def set_rel_descriptors(descriptor_list: list[FieldRelatedDescriptor], x: str):
            descriptor = get_related_attrs(getattr(model, x), x)
            descriptor_list.append(descriptor)
            rel_cache[x] = descriptor

        for x in vars(model):
            attr_type = type(getattr(model, x))

            if attr_type is ForwardOneToOneDescriptor:
                set_rel_descriptors(cache.forward_one_to_one_list, x)

            elif attr_type is ForwardManyToOneDescriptor:
                set_rel_descriptors(cache.forward_many_to_one_list, x)

            elif attr_type is ManyToManyDescriptor:
                set_rel_descriptors(cache.many_to_many_list, x)

            elif attr_type is ReverseManyToOneDescriptor:
                set_rel_descriptors(cache.reverse_many_to_one_list, x)

            elif attr_type is ReverseOneToOneDescriptor:
                set_rel_descriptors(cache.reverse_one_to_one_list, x)

            elif attr_type is ForeignKeyDeferredAttribute:
                set_field_descriptors(cache.id_list, x)

            elif attr_type is DeferredAttribute:
                set_field_descriptors(cache.field_list, x)

        cache.field_list = list(set(cache.field_list))
        cache.id_list = list(set(cache.id_list))
        cache.many_to_many_list = list(set(cache.many_to_many_list))
        cache.reverse_many_to_one_list = list(set(cache.reverse_many_to_one_list))
        cache.reverse_one_to_one_list = list(set(cache.reverse_one_to_one_list))
        cache.forward_many_to_one_list = list(set(cache.forward_many_to_one_list))
        cache.forward_one_to_one_list = list(set(cache.forward_one_to_one_list))

        cls._populate_parents(cache)

        SERIALIZER_DEPTHS[cls.get_serializer_path()] = cls.depth

    @classmethod
    def _get_field_names(cls, l: list[FieldDescriptor | FieldRelatedDescriptor]) -> list[str]:
        return [x.field_name for x in set(l)]

    @classmethod
    def _get_field_serializers(cls, l: list[FieldDescriptor]) -> dict[str, callable]:
        return dict([(x.field_name, x.serializer) for x in l if x.serializer is not None])

    @classmethod
    def _check_settings(cls):
        assert cls.depth > 0, "Depth must be greater than 0"
        assert all(isinstance(x, str) for x in cls.fields.keys()), "fields key must be a strings"
        assert isinstance(cls.filters, Iterable), "filters must be an array of strings"
        assert all(isinstance(x, str) for x in cls.filters), "filters must be an array of strings"
        assert all(isinstance(x, str) for x in cls.preselected), "preselected must be an array of strings"
        for field in cls.fields.values():
            assert all(isinstance(x, str) for x in field), "fields value must be an array of strings"

        field_list = cls._get_field_names(cls.cache.field_list)
        id_list = cls._get_field_names(cls.cache.id_list)

        m2m_list = cls._get_field_names(cls.cache.many_to_many_list + cls.cache.reverse_many_to_one_list)
        o2_list = cls._get_field_names(
            cls.cache.forward_one_to_one_list + cls.cache.reverse_one_to_one_list + cls.cache.forward_many_to_one_list
        )
        cls._field_list = field_list
        cls._id_list = id_list
        cls._m2m_list = m2m_list
        cls._o2_list = o2_list

        for key, fields in cls.fields.items():
            assert isinstance(fields, tuple), f"Set {key} must be a tuple[...str], got {type(fields).__name__}"

            set_name = key

            for field in fields:

                if "[" in field:
                    dot = "." in field
                    if dot:
                        key, forward = field.split(".")

                    else:
                        key, res = cls._get_expand_sets(field)

                    if key not in cls._children_sets:
                        cls._children_sets[key] = {
                            "parents": set(),
                            "sets": set(),
                            "forward": set(),
                        }

                    if dot:
                        cls._children_sets[key]["forward"].add(forward)
                    else:
                        cls._children_sets[key]["sets"] |= res

                    cls._children_sets[key]["parents"].add(set_name)

                    field = key

                field = cls._rewrites.get(field, field)

                if field in field_list or field + "_id" in id_list or field in m2m_list or field in o2_list:
                    continue

                assert (
                    0
                ), f"Field '{field}' not found in model '{cls.model.__name__}', available fields: {[x for x in vars(cls.model) if not x.startswith('_')]}"

        for field in cls.preselected:
            if field in field_list:
                continue

            if field + "_id" in id_list:
                continue

            assert 0, f"Preselected field '{field}' not found in model '{cls.model.__name__}'"

        for filter in cls.filters:
            original_filter = filter
            filter = cls._rewrites.get(filter, filter)
            if filter in field_list:
                cls._filter_map[filter] = None

                for field in cls.cache.field_list:
                    if field.field_name == filter:
                        cls._filter_map[filter] = field.query_handler
                        break

                continue

            if filter + "_id" in id_list:
                cls._filter_map[filter] = None

                for field in cls.cache.id_list:
                    if field.field_name == filter + "_id":
                        cls._filter_map[filter] = field.query_handler
                        break

                continue

            if filter in m2m_list:
                cls._filter_map[filter] = None

                for field in cls.cache.many_to_many_list:
                    if field.field_name == filter:
                        cls._filter_map[filter] = field.query_handler
                        break

                if cls._filter_map[filter]:
                    continue

                for field in cls.cache.reverse_many_to_one_list:
                    if field.field_name == filter:
                        cls._filter_map[filter] = field.query_handler
                        break

                continue

            if filter in o2_list:
                cls._filter_map[filter] = None

                for field in cls.cache.forward_one_to_one_list:
                    if field.field_name == filter:
                        cls._filter_map[filter] = field.query_handler
                        break

                if cls._filter_map[filter]:
                    continue

                for field in cls.cache.reverse_one_to_one_list:
                    if field.field_name == filter:
                        cls._filter_map[filter] = field.query_handler
                        break

                if cls._filter_map[filter]:
                    continue

                for field in cls.cache.forward_many_to_one_list:
                    if field.field_name == filter:
                        cls._filter_map[filter] = field.query_handler
                        break

                continue

            filter = original_filter
            assert 0, f"Filter '{filter}' not found in model '{cls.model.__name__}'"

        cls._serializers = {
            **cls._get_field_serializers(cls.cache.id_list),
            **cls._get_field_serializers(cls.cache.field_list),
            # **cls._get_field_serializers(cls.cache.many_to_many_list),
        }

    @classmethod
    def _get_related_serializers(cls):
        model = cls.model
        key = model._meta.app_label + "." + model.__name__
        cache = MODEL_CACHE.get(key)

        fields = (
            cache.many_to_many_list
            + cache.reverse_many_to_one_list
            + cache.reverse_one_to_one_list
            + cache.forward_many_to_one_list
            + cache.forward_one_to_one_list
        )

        for field in fields:
            field_name = cls.rewrites.get(field.field_name, field.field_name)
            if hasattr(cls, field_name):
                cls._related_serializers[field_name] = getattr(cls, field_name)

    # @classmethod
    # def _build_lookup_mapping(cls):

    #     # if hasattr(field, "m2m_field_name"):
    #     #     cls._lookups[name] = field.m2m_field_name()
    #     return cls._lookups

    @classmethod
    def _prepare_fields(cls):
        if hasattr(cls, "preselected") is False:
            cls.preselected = ()

        cls._lookups: dict[str, str] = {}
        if not hasattr(cls, "filters"):
            cls.filters: list[str] = []

        cls._filter_map: dict[str, QueryHandler | None] = {}

        cls._rewrites = {v: k for k, v in cls.rewrites.items()}
        cls._get_related_fields()
        cls._check_settings()
        cls._get_related_serializers()
        cls._lookups = cls.cache.lookup_rewrites


class Serializer(SerializerMetaBuilder):
    _serializer_instances: dict[str, Type["Serializer"]]
    sort_by: str = "pk"
    ttl: int | None = None
    cache_control: str | None = None
    revalidate: Callable[[], None] | None = None

    def _prefetch(self, qs: QuerySet):
        annotated = {}
        only = set()
        selected = set()
        for parsed_field in self._parsed_fields:
            if parsed_field in self._m2m_list or parsed_field in self._o2_list:
                field = self._rewrites.get(parsed_field, parsed_field)
                x = self.rel[field]
                field_name = x.field_name.replace("_set", "")
                annotated[f"__count_{x.field_name}"] = Count(field_name)

            if parsed_field not in self._o2_list and parsed_field not in self._m2m_list:
                only.add(parsed_field)

        if annotated:
            qs = qs.annotate(**annotated)

        for key, serializer in self._serializer_instances.items():
            children_sets = self._children_sets.get(key)

            if any(x in children_sets["parents"] for x in self._expand_sets):
                serializer.init(sets=children_sets["sets"] | children_sets["forward"], depth=self.depth - 1)

            else:
                serializer.init(sets=set(), depth=self.depth - 1)

            if key in self._o2_list:
                child_fields, child_expands, child_cache = serializer.manage()
                only |= set([f"{key}__{x}" for x in child_fields])

                if child_fields:
                    selected.add(key)

        for field in self.preselected:
            only.add(field)

        # this doesn't work, the only must include
        qs = qs.select_related(*selected).only(*only)
        return qs

    def _serialize(self, instance: models.Model) -> dict:
        data = {}

        for field in self._parsed_fields:
            key = self.rewrites.get(field, field)
            data[key] = getattr(instance, field, None)

            if field in self._field_list:
                serializer = self._serializers.get(field, None)
                if serializer:
                    data[key] = serializer(data[field])

            elif field + "_id" in self._id_list:
                forward = field in self._children_sets

                if forward and field in self._expands and hasattr(self, field):
                    ser = self._serializer_instances[field]
                    qs = data[field]

                    data[key] = ser._instance(qs)
                else:
                    data[key] = pk_serializer(data[field])

            elif field in self._m2m_list:
                parsed = self.rewrites.get(field, field)

                if parsed in self._children_sets and parsed in self._expands and hasattr(self, parsed):
                    ser = self._serializer_instances[parsed]

                    qs = data[parsed]
                    count = getattr(instance, f"__count_{field}", None)
                    query_param = self.cache.query_params.get(field)
                    data[key] = ser._instances(
                        qs.all(),
                        count,
                        extra={query_param + ".pk": getattr(instance, "pk", None)},
                    )

                else:
                    path = None
                    ser = self._serializer_instances.get(parsed)

                    if ser is None and hasattr(self, parsed):
                        ser = getattr(self, parsed)

                    if ser:
                        path = ser.path

                    m2m = getattr(instance, field)
                    count = getattr(instance, f"__count_{field}", None)
                    query_param = self.cache.query_params.get(field)

                    data[key] = self._wraps_pagination(
                        m2m.all().only("pk"),
                        count,
                        pks=True,
                        path=path,
                        extra={query_param + ".pk": getattr(instance, "pk", None)},
                    )

        return data

    def _set_fields(self) -> list[str]:
        self._expands = set()
        sets = set(["default"])

        if self._parent_sets is not None:
            sets = self._parent_sets | sets

        elif self.request is not None:
            sets_param = self.request.GET.get("sets")
            if sets_param:
                for set_name in sets_param.split(","):
                    if set_name:
                        sets.add(set_name)

        for key in sets:
            key = self.rewrites.get(key, key)
            if key in self.fields:
                fields = []
                for field in self.fields[key]:
                    if "[" in field and self.depth >= 0:
                        field = field.split("[")[0]
                        self._expands.add(field)

                    if "." in field:
                        continue

                    field = self._rewrites.get(field, field)
                    fields.append(field)

                for field in fields:
                    self._parsed_fields.add(field)

        for expand in self._expands:
            serializer = self._related_serializers.get(expand)
            if serializer is None:
                continue

            instance = serializer()
            self._serializer_instances[expand] = instance

    def manage(self):
        self._set_fields()
        self.lock = True
        return self._parsed_fields, self._expands, self.cache

    def _wraps_pagination(
        self,
        qs: QuerySet,
        count: Optional[int] = None,
        pks: bool = False,
        path: Optional[str] = "-",
        extra: Optional[dict[str, Any]] = None,
    ):
        if count is None:
            count = qs.count()

        if path == "-":
            path = self.path

        if extra is None:
            extra = {}

        base = {
            "count": count,
        }

        if pks:
            base["results"] = [pk_serializer(x) for x in qs[:PKS_LIMIT]]
        else:
            base["results"] = [self._serialize(x) for x in qs[:PKS_LIMIT]]

        if not path:
            return base

        offset = (math.ceil(count / PAGE_LIMIT) * PAGE_LIMIT) - PAGE_LIMIT
        obj = {
            **base,
            "next": None,
            "previous": None,
            "first": update_querystring(
                path,
                {
                    "limit": PAGE_LIMIT,
                    "offset": 0,
                    **extra,
                },
            ),
            "last": update_querystring(
                path,
                {
                    "limit": PAGE_LIMIT,
                    "offset": offset if offset >= 0 else 0,
                    **extra,
                },
            ),
        }
        if count > PAGE_LIMIT:
            obj["next"] = update_querystring(
                path,
                {
                    "limit": PAGE_LIMIT,
                    "offset": PAGE_LIMIT,
                    **extra,
                },
            )

        obj["results"] = obj.pop("results")

        return obj

    @classmethod
    def _get_query_value(
        cls, handler: QueryHandler, error_handler: Optional[QueryHandler], parents: list[str], key: str, value: str
    ):
        def get_key():
            if parents:
                return ".".join(parents) + "." + key

            return key

        if error_handler:
            try:
                return handler(value)
            except Exception:
                raise ValidationException(f"Invalid value for field {get_key()}")

        return handler(value)

    @classmethod
    def _validate_filter(cls, x: str, parents: Optional[list[str]] = None) -> FilterOperation | None:
        if parents is None:
            parents = []

        pattern = re.compile(r"^(\w+)\[(.*)\]$")

        if "=" in x:
            if "![" in x.split("=")[0] and "]=" in x:
                pattern = re.compile(r"^(.+)\!\[(.+)\]=(.+)$")
                match = pattern.search(x)
                if not match:
                    raise ValidationException(
                        f"Invalid filter {x}, format should be `field[operation]=value` or `field![operation]=value`"
                    )

                key, operation, value = match.groups()

                handler, error_handler, supported_operations = cls._filter_map[key]

                operations = operation.split(",")
                for operation in operations:
                    if operation not in supported_operations:
                        raise ValidationException(f"Operation `{operation}` not supported for field {key}")

                key = cls._rewrites.get(key, key)

                return None, {
                    "field": key,
                    "operation": operation.replace(",", "__"),
                    "value": value,
                    "parents": parents,
                }

            elif "[" in x.split("=")[0] and "]=" in x:
                pattern = re.compile(r"^(.+)\[(.+)\]=(.+)$")
                match = pattern.search(x)
                if not match:
                    raise ValidationException(
                        f"Invalid filter {x}, format should be `field[operation]=value` or `field![operation]=value`"
                    )
                key, operation, value = match.groups()

                handler, error_handler, supported_operations = cls._filter_map[key]

                operations = operation.split(",")
                for operation in operations:
                    if operation not in supported_operations:
                        raise ValidationException(f"Operation `{operation}` not supported for field {key}")

                key = cls._rewrites.get(key, key)

                return {
                    "field": key,
                    "operation": operation.replace(",", "__"),
                    "value": value,
                    "parents": parents,
                }, None

            elif "!<=" in x:
                field, value = x.split("!<=")
                handler, error_handler, supported_operations = cls._filter_map[field]

                operation = "lte"
                if operation not in supported_operations:
                    raise ValidationException(f"Operation `!<=` not supported for field {field}")

                value = cls._get_query_value(handler, error_handler, parents, field, value)
                field = cls._rewrites.get(field, field)

                return None, {"field": field, "operation": operation, "value": value, "parents": parents}

            elif "!>=" in x:
                field, value = x.split("!>=")
                handler, error_handler, supported_operations = cls._filter_map[field]

                operation = "gte"
                if operation not in supported_operations:
                    raise ValidationException(f"Operation `!<=` not supported for field {field}")

                value = cls._get_query_value(handler, error_handler, parents, field, value)
                field = cls._rewrites.get(field, field)

                return None, {"field": field, "operation": operation, "value": value, "parents": parents}

            elif "<=" in x:
                field, value = x.split("<=")
                handler, error_handler, supported_operations = cls._filter_map[field]

                operation = "lte"
                if operation not in supported_operations:
                    raise ValidationException(f"Operation `>=` not supported for field {field}")

                value = cls._get_query_value(handler, error_handler, parents, field, value)
                field = cls._rewrites.get(field, field)

                return {"field": field, "operation": operation, "value": value, "parents": parents}, None

            elif ">=" in x:
                field, value = x.split(">=")
                handler, error_handler, supported_operations = cls._filter_map[field]

                operation = "gte"
                if operation not in supported_operations:
                    raise ValidationException(f"Operation `>=` not supported for field {field}")

                value = cls._get_query_value(handler, error_handler, parents, field, value)
                field = cls._rewrites.get(field, field)

                return {"field": field, "operation": operation, "value": value, "parents": parents}, None

            elif "!~=" in x:
                field, value = x.split("!~=")
                handler, error_handler, supported_operations = cls._filter_map[field]

                operation = "iexact"
                if operation not in supported_operations:
                    raise ValidationException(f"Operation `~=` not supported for field {field}")

                value = cls._get_query_value(handler, error_handler, parents, field, value)

                if "," in value:
                    value = value.split(",")
                    operation += "__in"

                field = cls._rewrites.get(field, field)

                return None, {"field": field, "operation": operation, "value": value, "parents": parents}

            elif "~=" in x:
                field, value = x.split("~=")
                handler, error_handler, supported_operations = cls._filter_map[field]

                operation = "iexact"
                if operation not in supported_operations:
                    raise ValidationException(f"Operation `~=` not supported for field {field}")

                value = cls._get_query_value(handler, error_handler, parents, field, value)

                if "," in value:
                    value = value.split(",")
                    operation += "__in"

                field = cls._rewrites.get(field, field)

                return {"field": field, "operation": operation, "value": value, "parents": parents}, None

            elif "!=" in x:
                field, value = x.split("!=")
                handler, error_handler, supported_operations = cls._filter_map[field]

                operation = "exact"
                if operation not in supported_operations:
                    raise ValidationException(f"Operation `!=` not supported for field {field}")

                value = cls._get_query_value(handler, error_handler, parents, field, value)

                if "," in value:
                    value = value.split(",")
                    operation = "in"

                field = cls._rewrites.get(field, field)

                return None, {"field": field, "operation": operation, "value": value, "parents": parents}

            else:
                field, value = x.split("=")
                handler, error_handler, supported_operations = cls._filter_map[field]

                operation = "exact"
                if operation not in supported_operations:
                    raise ValidationException(f"Operation `=` not supported for field {field}")

                value = cls._get_query_value(handler, error_handler, parents, field, value)

                if "," in value:
                    value = value.split(",")
                    operation = "in"

                field = cls._rewrites.get(field, field)

                return {"field": field, "operation": operation, "value": value, "parents": parents}, None

        elif "!<" in x:
            field, value = x.split("!<")
            handler, error_handler, supported_operations = cls._filter_map[field]

            operation = "lt"
            if operation not in supported_operations:
                raise ValidationException(f"Operation `!<` not supported for field {field}")

            value = cls._get_query_value(handler, error_handler, parents, field, value)
            field = cls._rewrites.get(field, field)

            return None, {"field": field, "operation": operation, "value": value, "parents": parents}

        elif "!>" in x:
            field, value = x.split("!>")
            handler, error_handler, supported_operations = cls._filter_map[field]

            operation = "gt"
            if operation not in supported_operations:
                raise ValidationException(f"Operation `!>` not supported for field {field}")

            value = cls._get_query_value(handler, error_handler, parents, field, value)
            field = cls._rewrites.get(field, field)

            return None, {"field": field, "operation": operation, "value": value, "parents": parents}

        elif "<" in x:
            field, value = x.split("<")
            handler, error_handler, supported_operations = cls._filter_map[field]

            operation = "lt"
            if operation not in supported_operations:
                raise ValidationException(f"Operation `<` not supported for field {field}")

            value = cls._get_query_value(handler, error_handler, parents, field, value)
            field = cls._rewrites.get(field, field)

            return {"field": field, "operation": operation, "value": value, "parents": parents}, None

        elif ">" in x:
            field, value = x.split(">")
            handler, error_handler, supported_operations = cls._filter_map[field]

            operation = "gt"
            if operation not in supported_operations:
                raise ValidationException(f"Operation `>` not supported for field {field}")

            value = cls._get_query_value(handler, error_handler, parents, field, value)
            field = cls._rewrites.get(field, field)

            return {"field": field, "operation": operation, "value": value, "parents": parents}, None

        return None, None

    @classmethod
    def _validate_child_filter(
        cls, x: str, parents: Optional[list[str]] = None
    ) -> tuple[FilterOperation, FilterOperation] | None:

        if parents is None:
            parents = []

        selector = "="
        if "~" in x:
            selector = "~"

        elif "<" in x:
            selector = "<"

        elif ">" in x:
            selector = ">"

        elif "!" in x:
            selector = "!"

        elif "[" in x:
            selector = "["

        if "." not in x.split(selector)[0]:
            return cls._validate_filter(x, parents)

        child, *rest = x.split(".")
        child = x.split(selector)[0].split(".")[0]

        ser: Serializer | None = getattr(cls, child, None)
        if ser is None:
            return None, None

        child = cls._rewrites.get(child, child)
        forward = cls._lookups.get(child, child) if child.endswith("_set") else child

        return ser._validate_child_filter(".".join(rest), parents + [forward])

    def _query_filter(self, qs: QuerySet) -> QuerySet:
        def build_filter(filters: list[FilterOperation]):
            named = {}
            unnamed = []
            for filter in filters:
                is_iexact_in = filter["operation"] == "iexact__in" or filter["operation"] == "in__iexact"

                if filter["parents"] and is_iexact_in:
                    query = Q()
                    for value in filter["value"]:
                        kwargs = {}
                        kwargs["__".join(filter["parents"]) + f"__{filter['field']}__iexact"] = value
                        query |= Q(**kwargs)

                    unnamed.append(query)

                elif filter["parents"]:
                    named["__".join(filter["parents"]) + f"__{filter['field']}__{filter['operation']}"] = filter[
                        "value"
                    ]

                elif is_iexact_in:
                    query = Q()
                    for value in filter["value"]:
                        kwargs = {}
                        kwargs[f"{filter['field']}__iexact"] = value
                        query |= Q(**kwargs)

                    unnamed.append(query)

                else:
                    named[f"{filter['field']}__{filter['operation']}"] = filter["value"]

            return unnamed, named

        query_filters: list[FilterOperation] = []
        exclude_filters: list[FilterOperation] = []

        for x in (self.request.META.get("QUERY_STRING") or "").split("&"):
            if x.startswith("sets=") or x.startswith("sort=") or x.startswith("limit=") or x.startswith("offset="):
                continue

            if "." in x.split("=")[0]:
                query, exclude = self._validate_child_filter(x)

                if not query and not exclude:
                    continue

                if query:
                    query_filters.append(query)

                if exclude:
                    exclude_filters.append(exclude)

            else:
                query, exclude = self._validate_filter(x)

                if query:
                    query_filters.append(query)

                if exclude:
                    exclude_filters.append(exclude)

        if query_filters:
            args, kwargs = build_filter(query_filters)
            qs = qs.filter(*args, **kwargs)

        if exclude_filters:
            args, kwargs = build_filter(exclude_filters)
            qs = qs.exclude(*args, **kwargs)

        return qs

    @classmethod
    def help(cls, depth: Optional[int] = None):
        original_depth = depth

        def get_field_info(field: FieldDescriptor):
            attributes = {
                "null": field.null,
                "blank": field.blank,
                "editable": field.editable,
                "is_relation": field.is_relation,
                "primary_key": field.primary_key,
                "type": field.type.__name__,
                "default": field.default if field.default is not django_fields.NOT_PROVIDED else None,
                "help_text": field.help_text,
            }

            if field.choices:
                attributes["choices"] = field.choices

            if field.max_length:
                attributes["choices"] = field.max_length

            return {"name": field.field_name, "attributes": attributes}

        def get_rel_info(field: FieldRelatedDescriptor):
            # field_name: str,
            return {
                "name": field.field_name,
                "metadata": {
                    "null": field.nullable,
                    "blank": field.blank,
                    "editable": field.editable,
                    "is_relation": field.is_relation,
                    "primary_key": field.primary_key,
                    "type": field.path,
                    "default": field.default if field.default is not django_fields.NOT_PROVIDED else None,
                    "help_text": field.help_text,
                },
            }

        if depth is None:
            depth = cls.depth

        elif cls.depth == 0:
            return

        sets = []
        field_map = {}
        id_map = {}
        rel_map = {}

        for field in cls.cache.field_list:
            field_map[field.field_name] = field

        for field in cls.cache.id_list:
            id_map[field.field_name] = field

        m2m = [*cls.cache.many_to_many_list, *cls.cache.reverse_many_to_one_list]
        o2 = [
            *cls.cache.forward_one_to_one_list,
            *cls.cache.reverse_one_to_one_list,
            *cls.cache.forward_many_to_one_list,
        ]

        for field in m2m + o2:
            rel_map[field.field_name] = field

        inherited_filters = set()

        for s in cls.fields:
            fields = []
            expandables = []
            for field_name in cls.fields[s]:
                if field_info := field_map.get(field_name):
                    fields.append(
                        {
                            "name": field_name,
                            **get_field_info(field_info),
                        }
                    )

                else:

                    if "[" in field_name:
                        field_name, child_sets = field_name.split("[")
                        child_sets = child_sets.replace("]", "")
                        expandable = True
                    else:
                        child_sets = None
                        expandable = False

                    original_field_name = cls._rewrites.get(field_name, field_name)

                    if rel_info := rel_map.get(original_field_name):
                        id_info = id_map.get(field_name + "_id")
                        if expandable:
                            child_help = None
                            ser: Serializer | None = getattr(cls, field_name, None)
                            if ser:
                                child_help = ser.help(depth - 1)

                            if id_info:
                                obj = {
                                    **get_rel_info(rel_info),
                                    "name": field_name,
                                    "type": "list" if original_field_name in cls._m2m_list else "object",
                                }
                                if child_help:
                                    obj["sets"] = child_help["sets"]
                                    for x in child_help["filters"]:
                                        inherited_filters.add(f"{field_name}.{x}")

                                expandables.append(obj)

                            else:
                                obj = {
                                    **get_rel_info(rel_info),
                                    "name": field_name,
                                    "type": "list" if original_field_name in cls._m2m_list else "object",
                                }
                                if child_help:
                                    obj["sets"] = child_help["sets"]
                                    for x in child_help["filters"]:
                                        inherited_filters.add(f"{field_name}.{x}")

                                expandables.append(obj)

                        elif id_info:
                            fields.append(
                                {
                                    **get_field_info(id_info),
                                    "name": field_name,
                                    "type": "pks" if original_field_name in cls._m2m_list else "pk",
                                }
                            )

            sets.append(
                {
                    "set": s,
                    "fields": fields,
                    "relationships": expandables,
                }
            )

        result = {"filters": sorted([*cls.filters, *inherited_filters]), "sets": sets}

        if original_depth is None:
            return HttpResponse(json.dumps(result), status=200, headers={"Content-Type": "application/json"})

        return result

    def filter(self, *args: Any, **kwargs: Any) -> List[dict[str, Any]] | dict[str, Any]:
        self._verify_headers()

        if "help" in self.request.META.get("QUERY_STRING"):
            for x in (self.request.META.get("QUERY_STRING") or "").split("&"):
                if x == "help":
                    return self.help()

        cache = get_cache(
            serializer=self.get_serializer_path(),
            params=(args, kwargs),
            query=self.request.META.get("QUERY_STRING").split("&"),
            headers=self.request.headers,
        )
        if cache:
            return cache

        self._set_fields()
        qs = self.model.objects.filter(*args, **kwargs).order_by(self.sort_by)
        qs = self._query_filter(qs)
        qs = self._prefetch(qs)

        return set_cache(
            serializer=self.get_serializer_path(),
            value=self._wraps_pagination(qs),
            ttl=self.ttl,
            params=(args, kwargs),
            query=self.request.META.get("QUERY_STRING").split("&"),
            headers=self.request.headers,
            cache_control=self.cache_control,
        )

    @sync_to_async
    def afilter(self, *args: Any, **kwargs: Any) -> List[dict[str, Any]]:
        return self.filter(*args, **kwargs)

    def _verify_headers(self):
        accept = self.request.headers.get("Accept", "application/json")
        for x in ["application/json", "*/*", "application/*", "*/json"]:
            if x in accept:
                return

        raise ValidationException("Accept header must be application/json")

    def get(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        self._verify_headers()

        if "help" in self.request.META.get("QUERY_STRING"):
            for x in (self.request.META.get("QUERY_STRING") or "").split("&"):
                if x == "help":
                    return self.help()

        cache = get_cache(
            serializer=self.get_serializer_path(),
            params=(args, kwargs),
            query=self.request.META.get("QUERY_STRING").split("&"),
            headers=self.request.headers,
        )
        if cache:
            return cache

        self._set_fields()
        qs = self.model.objects.filter(*args, **kwargs).order_by(self.sort_by)
        qs = self._query_filter(qs)
        qs = self._prefetch(qs)
        qs = qs.first()
        if qs is None:
            return None

        return set_cache(
            serializer=self.get_serializer_path(),
            value=self._serialize(qs),
            ttl=self.ttl,
            params=(args, kwargs),
            query=self.request.META.get("QUERY_STRING").split("&"),
            headers=self.request.headers,
            cache_control=self.cache_control,
        )

    @sync_to_async
    def aget(self, *args: Any, **kwargs: Any) -> dict[str, Any] | None:
        return self.get(*args, **kwargs)

    def _instances(
        self,
        qs: QuerySet[models.Model],
        count: Optional[int] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> List[dict[str, Any]]:
        self._set_fields()

        qs = qs.order_by(self.sort_by)
        qs = self._prefetch(qs)
        return self._wraps_pagination(qs, count, extra=extra)

    @sync_to_async
    def _ainstances(
        self, qs: QuerySet[models.Model], count: Optional[int] = None, extra: Optional[dict[str, Any]] = None
    ) -> List[dict[str, Any]]:
        return self._instances(qs, count, extra)

    def _instance(self, instance: models.Model) -> dict[str, Any] | None:
        return self._serialize(instance)

    @sync_to_async
    def ainstance(self, instance: models.Model) -> dict[str, Any] | None:
        return self._instance(instance)

    def __init_subclass__(cls):
        cls._prepare_fields()
        super().__init_subclass__()

    def __init__(
        self,
        request: Optional[HttpRequest | AsyncRequest] = None,
        sets: Optional[Collection[str]] = None,
    ):
        self.request = request

        if request and (sort_by := request.GET.get("sort")):
            self.sort_by = sort_by

        self.init(sets)

    def init(
        self,
        sets: Optional[Collection[str]] = None,
        depth: Optional[int] = None,
    ) -> None:
        self._serializer_instances: dict[str, Type["Serializer"]] = {}

        if depth is not None:
            self.depth = depth

        self._parsed_fields = set()

        if sets is not None:
            self._parent_sets = set(sets)
        else:
            self._parent_sets = None

        self._expand_sets = set()
