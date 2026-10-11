import uiautomation as auto

root = auto.GetRootControl()
print("Root:", root.Name, root.ControlTypeName)
children = root.GetChildren()
print(f"Total top-level children: {len(children)}")
for i, c in enumerate(children):
    print(f"{i}: [{c.ControlTypeName}] Name: '{c.Name}' Class: '{c.ClassName}' ProcessId: {c.ProcessId}")
