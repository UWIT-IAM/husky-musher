import json
from typing import Any, Optional, Type

from injector import inject, singleton
from redis import Redis

from husky_musher.settings import AppSettings


@singleton
class Cache:
    """
    A cache that uses a redis interface to perform simple gets and sets,
    with optional JSON-type conversion. If there is no REDIS_HOST set
    in the environment, a simple dictionary will be used instead (for local testing).
    """

    @inject
    def __init__(self, redis: Redis, settings: AppSettings):
        self.redis = redis
        self.prefix = f"{settings.app_name}:"

    def sanitize_key(self, key):
        if key and not key.startswith(self.prefix):
            return f"{self.prefix}{key}"
        return key

    @staticmethod
    def _sanitize_value(value: Any):
        """
        If the value is not already of a type supported by redis,
        assume it to be a something json-serializable, and attempt
        to serialize it.

        >>> Cache._sanitize_value({'foo': 'bar'})
        '{"foo": "bar"}'

        >>> Cache._sanitize_value(123)
        123

        >>> Cache._sanitize_value('123')
        '123'
        """
        if not isinstance(value, (bytes, str, int, float)):
            return json.dumps(value)
        return value

    def get(self, key, load_json: bool = False, cast_as: Type[Any] = None) -> Any:
        """
        Retrieves a value from the cache. Toggle load_json=True to
        assume the data is json, and deserialize it; otherwise,
        the type returned by redis will be honored (probably `bytes`).

        >>> self.set('foo', {'a': 'b'})

        >>> self.get('foo')
        '{"foo": {"a": "b"}}'

        >>> self.get('foo', load_json=True)
        {'a': 'b'}

        >>> class Blah:
        ...    def __init__(self, props: Dict[str, str]):
        ...        self.a = props.get('a')

        >>> self.get('foo', load_json=True, cast_as=Blah).a
        'b'
        """
        value = self.redis.get(self.sanitize_key(key))
        if value and load_json:
            return json.loads(value)
        if cast_as:
            return cast_as(value)
        return value

    def set(self, key: str, value: Any, expire_seconds: Optional[int] = None):
        """
        Adds an entry to the cache. If the entry is a serializable object,
        it will be converted to json. Otherwise, its underlying type will
        be preserved. Redis usually returns bytes for values that were stored;
        prepare to include the `cast_as` parameter in .get()

        Passing an unserializable object will result in a TypeError.

        >>> self.set('foo', 123)
        True
        >>> self.get('foo')
        b'123'
        >>> self.get('foo', cast_as=int)
        123

        >>> self.set('foo', {1, 2, 3})
        TypeError: Object of type set is not JSON serializable
        """
        key = self.sanitize_key(key)
        value = self._sanitize_value(value)
        self.redis.set(key, value, ex=expire_seconds)


class MockRedis:
    """
    For use when running without redis, so that there is
    no need for developers to install redis in order to maintain this application.
    """

    def __init__(self):
        self._values = {}

    def get(self, key):
        return self._values.get(key)

    def set(self, key, value, *args, **kwargs):
        self._values[key] = value
