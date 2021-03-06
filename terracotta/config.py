"""config.py

Terracotta settings parsing.
"""

from typing import Mapping, Any, Tuple, NamedTuple, Dict, Optional
import os
import json
import tempfile

from marshmallow import Schema, fields, validate, pre_load, post_load, ValidationError


class TerracottaSettings(NamedTuple):
    """Contains all settings for the current Terracotta instance."""
    #: Path to database
    DRIVER_PATH: str = ''

    #: Driver provider to use (sqlite, sqlite-remote, mysql; auto-detected by default)
    DRIVER_PROVIDER: Optional[str] = None

    #: Activate debug mode in Flask app
    DEBUG: bool = False

    #: Print profile information after every request
    FLASK_PROFILE: bool = False

    #: Send performance traces to AWS X-Ray
    XRAY_PROFILE: bool = False

    #: Default log level (debug, info, warning, error, critical)
    LOGLEVEL: str = 'warning'

    #: Size of raster file in-memory cache in bytes
    RASTER_CACHE_SIZE: int = 1024 * 1024 * 490  # 490 MB

    #: Tile size to return if not given in parameters
    DEFAULT_TILE_SIZE: Tuple[int, int] = (256, 256)

    #: Maximum size to use when lazy loading metadata (less is faster but less accurate)
    LAZY_LOADING_MAX_SHAPE: Tuple[int, int] = (1024, 1024)

    #: Compression level of output PNGs from 0-10
    PNG_COMPRESS_LEVEL: int = 1

    #: Timeout in seconds for database connections
    DB_CONNECTION_TIMEOUT: int = 10

    #: Path where cached remote SQLite databases are stored (when using sqlite-remote provider)
    REMOTE_DB_CACHE_DIR: str = os.path.join(tempfile.gettempdir(), 'terracotta')

    #: Time-to-live of remote database cache in seconds
    REMOTE_DB_CACHE_TTL: int = 10 * 60  # 10 min

    #: Resampling method to use when upsampling data (high zoom levels)
    UPSAMPLING_METHOD: str = 'cubic'

    #: Resampling method to use when downsampling data (low zoom levels)
    DOWNSAMPLING_METHOD: str = 'nearest'


AVAILABLE_SETTINGS: Tuple[str, ...] = tuple(TerracottaSettings._fields)


def _is_writable(path: str) -> bool:
    return os.access(os.path.dirname(path) or os.getcwd(), os.W_OK)


class SettingSchema(Schema):
    """Schema used to create and validate TerracottaSettings objects"""
    DRIVER_PATH = fields.String()
    DRIVER_PROVIDER = fields.String(allow_none=True)

    DEBUG = fields.Boolean()
    FLASK_PROFILE = fields.Boolean()
    XRAY_PROFILE = fields.Boolean()

    LOGLEVEL = fields.String(
        validate=validate.OneOf(['debug', 'info', 'warning', 'error', 'critical'])
    )

    RASTER_CACHE_SIZE = fields.Integer()

    DEFAULT_TILE_SIZE = fields.List(fields.Integer(), validate=validate.Length(equal=2))
    LAZY_LOADING_MAX_SHAPE = fields.List(fields.Integer(), validate=validate.Length(equal=2))

    PNG_COMPRESS_LEVEL = fields.Integer(validate=validate.Range(min=0, max=9))

    DB_CONNECTION_TIMEOUT = fields.Integer()
    REMOTE_DB_CACHE_DIR = fields.String(validate=_is_writable)
    REMOTE_DB_CACHE_TTL = fields.Integer()

    UPSAMPLING_METHOD = fields.String(
        validate=validate.OneOf(['nearest', 'linear', 'cubic', 'average'])
    )
    DOWNSAMPLING_METHOD = fields.String(
        validate=validate.OneOf(['nearest', 'linear', 'cubic', 'average'])
    )

    @pre_load
    def decode_lists(self, data: Dict[str, Any]) -> Dict[str, Any]:
        for var in ('DEFAULT_TILE_SIZE',):
            val = data.get(var)
            if val and isinstance(val, str):
                try:
                    data[var] = json.loads(val)
                except json.decoder.JSONDecodeError as exc:
                    raise ValidationError(f'Could not parse value for key {var} as JSON') from exc
        return data

    @post_load
    def make_settings(self, data: Dict[str, Any]) -> TerracottaSettings:
        # encode tuples
        for var in ('DEFAULT_TILE_SIZE',):
            val = data.get(var)
            if val:
                data[var] = tuple(val)

        return TerracottaSettings(**data)


def parse_config(config: Mapping[str, Any] = None) -> TerracottaSettings:
    """Parse given config dict and return new TerracottaSettings object"""
    config_dict = dict(config or {})

    for setting in AVAILABLE_SETTINGS:
        env_setting = f'TC_{setting}'
        if setting not in config_dict and env_setting in os.environ:
            config_dict[setting] = os.environ[env_setting]

    schema = SettingSchema()
    try:
        new_settings = schema.load(config_dict)
    except ValidationError as exc:
        raise ValueError('Could not parse configuration') from exc

    return new_settings
