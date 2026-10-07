"""Schema validation library, for the range of Home Assistant versions supported

Home Assistant 2026.10 replaced voluptuous with probatio, aliasing `voluptuous` to it at runtime
so that `import voluptuous` carries on working. Earlier versions, supported here until they are
more than 6 months old, only have voluptuous.

So voluptuous is still what is imported at runtime, whichever library that turns out to be, while
type checking is against probatio, since that is what the current Home Assistant type hints expect.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import probatio as vol
    from probatio import humanize
else:
    import voluptuous as vol
    from voluptuous import humanize

__all__ = ["humanize", "vol"]
