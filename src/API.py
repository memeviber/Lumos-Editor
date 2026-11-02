import logging

logger = logging.getLogger(__name__)


class LumosAPI:
    def __init__(self, wrapped_obj):
        super().__setattr__("_wrapped_obj", wrapped_obj)
        logger.debug("Initialized plugin API wrapper for %s", type(wrapped_obj).__name__)

    def __getattr__(self, name):
        if isinstance(self._wrapped_obj, dict):
            if name in self._wrapped_obj:
                attr = self._wrapped_obj[name]
            else:
                raise AttributeError(f"'LumosAPI' has no attribute '{name}'")
        else:
            attr = getattr(self._wrapped_obj, name)
        if callable(attr) or isinstance(attr, (int, str, bool, float, type(None))):
            return attr
        else:
            return LumosAPI(wrapped_obj=attr)

    def __setattr__(self, name, value):
        if name == "_wrapped_obj":
            super().__setattr__(name, value)
        else:
            logger.warning(
                "Plugin attempted to modify protected API attribute: %s", name
            )
            raise PermissionError(
                "Plugins are not allowed to modify the Lumos API or its objects."
            )

    def __delattr__(self, name):
        logger.warning("Plugin attempted to delete protected API attribute: %s", name)
        raise PermissionError(
            "Plugins are not allowed to delete attributes of the Lumos API."
        )
