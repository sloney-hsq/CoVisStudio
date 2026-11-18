"""Explicit model wire contract; domain/manual sources keep integer ranking counts."""

from copy import deepcopy

from jsonschema import ValidationError, validate


# The advertised model tools that expose the shared domain source schema
# (backend/model_tools.py). Internal and REST tools keep strict integer counts.
TOP_N_PATHS = {
    "revise_analysis": ("top_n",),
    "create_chart": ("source", "top_n"),
}
MODEL_TOP_N_SCHEMA = {
    "type": ["string", "null"], "pattern": r"^[1-9][0-9]*(?![\s\S])",
    "description": 'Dynamic ranking count as a positive decimal string, for example "3". '
                   'Use null to clear ranking. Omit to retain the current rule.',
}


def model_tool_definitions(definitions):
    """Advertise the same explicit wire representation in every study condition."""
    tools = deepcopy(definitions)
    for tool in tools:
        function = tool["function"]
        path = TOP_N_PATHS.get(function["name"])
        if path is None:
            continue
        schema = function["parameters"]
        for field in path[:-1]:
            schema = schema["properties"][field]
        schema["properties"][path[-1]] = deepcopy(MODEL_TOP_N_SCHEMA)
    return tools


def compile_model_arguments(name, arguments, definitions):
    """Validate raw wire arguments, then compile the declared count to a domain integer.

    This accepts no numeric alternative and performs no string/object repair. The caller
    archives native arguments before this boundary; the input object stays untouched.
    """
    schema = next((tool["function"]["parameters"] for tool in definitions
                   if tool["function"]["name"] == name), None)
    if schema is None:
        raise ValidationError(f"Unknown tool {name!r}; use one of the advertised tools.")
    validate(arguments, schema)
    compiled = deepcopy(arguments)
    path = TOP_N_PATHS.get(name)
    if path is not None:
        container = compiled
        for field in path[:-1]:
            if field not in container:
                return compiled
            container = container[field]
        field = path[-1]
        if field in container and container[field] is not None:
            container[field] = int(container[field])
    return compiled
