export function buildTree(departments) {
  const byId = new Map(departments.map((d) => [d.id, { ...d, children: [] }]));
  const roots = [];
  for (const node of byId.values()) {
    const parent = node.parent_id == null ? null : byId.get(node.parent_id);
    (parent ? parent.children : roots).push(node);
  }
  const sort = (nodes) => nodes.sort((a, b) => a.name.localeCompare(b.name)).forEach((n) => sort(n.children));
  sort(roots);
  return roots;
}
