"""Forward-only matching for the fixed descendant chains used by providers."""
from bs4 import Tag


def _descendants(root, *components):
    """Yield a CSS descendant chain in document order, once per matching tag.

    Components must be internal, single compound selectors (no combinators).
    Soup Sieve matches each component locally; ancestor-prefix matches are
    carried forward instead of repeatedly searching backwards up the tree.
    Work and storage are O(tags * components), including deeply nested markup.
    """
    queries = [root.css.compile(component) for component in components]
    empty = (False,) * len(queries)
    states = {}

    def visit(tag, parent):
        local = [query.match(tag) for query in queries]
        states[id(tag)] = tuple(
            parent[i] or (local[i] and (i == 0 or parent[i - 1]))
            for i in range(len(queries))
        )
        return local[-1] and (len(queries) == 1 or parent[-2])

    # CSS selection can use the root and its ancestors for the left side of a
    # chain, but only descendants of root may be returned.
    parent = empty
    for tag in reversed([root, *root.parents]):
        visit(tag, parent)
        parent = states[id(tag)]
    for tag in root.descendants:
        if isinstance(tag, Tag) and visit(tag, states[id(tag.parent)]):
            yield tag


def _find_descendant(root, *components):
    return next(_descendants(root, *components), None)
