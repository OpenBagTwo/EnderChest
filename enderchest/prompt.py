"""Utilities for helping build interactive prompts"""

CURSOR = "==>"

# https://stackoverflow.com/a/18472142
YES = ("y", "yes", "t", "true", "on", "1")

NO = ("n", "no", "f", "false", "off", "0")


def prompt(message: str, suggestion: str | None = None) -> str:
    """Prompt the user and return the response

    Parameters
    ----------
    message : str
        The prompt message
    suggestion : str, optional
        A suggested input. If None is provided, no suggestion will be shown.

    Returns
    -------
    str
        The user-provided response

    Notes
    -----
    - The output will be stripped of trailing and leading whitespace, but no
      other validation or processing will be used.
    - Regardless of whether a suggestion is provided, if the user provides an
      empty input, this method will return an empty string. To reiterate: the
      suggestion *does not serve* as a default / fallback value.
    """
    lines = message.splitlines() + [""]
    message = "\n".join(f"{CURSOR} {line}" for line in lines)
    if suggestion is not None:
        message += f"[{suggestion}] "
    return input(message)


def confirm(default: bool) -> bool:
    """Confirm that the user wishes to continue

    Parameters
    ----------
    default : bool
        Whether the default selection should be True (yes) or False (no)

    Returns
    -------
    bool
        Whether the user has opted to continue
    """

    response = prompt("Do you wish to continue?", "Y/n" if default else "y/N")

    if response == "":
        return default

    if response in YES:
        return True

    return False
