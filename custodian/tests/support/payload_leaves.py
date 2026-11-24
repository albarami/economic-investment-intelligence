"""Shared leaf traversal and replacement for invented hostile payloads."""


def leaves(value, path=()):
    if isinstance(value, dict) and value:
        return [
            leaf for key, item in value.items() for leaf in leaves(item, (*path, key))
        ]
    if isinstance(value, list) and value:
        return [
            leaf
            for index, item in enumerate(value)
            for leaf in leaves(item, (*path, index))
        ]
    return [path]


def replace_leaf(value, path, hostile):
    from copy import deepcopy

    changed = deepcopy(value)
    if not path:
        return hostile
    parent = changed
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = hostile
    return changed
