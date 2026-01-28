# Architecture Diagrams

This folder contains D2 architecture diagrams for the Reflexio project.

## Available Diagrams

| File | Description |
|------|-------------|
| `server_architecture.d2` | Compact overview of `reflexio/server/` with all layers |
| `service_layer_detail.d2` | Detailed service layer: GenerationService, extractors, configs, versioning |

## Prerequisites

Install D2 (diagram language):

```bash
# macOS
brew install d2

# Linux
curl -fsSL https://d2lang.com/install.sh | sh -s --

# Or see: https://d2lang.com/tour/install
```

## Rendering Diagrams

```bash
# Render to SVG (recommended)
d2 server_architecture.d2 server_architecture.svg

# Watch mode (auto-refresh on changes)
d2 --watch server_architecture.d2 server_architecture.svg

# Render to PNG
d2 server_architecture.d2 server_architecture.png
```

**VS Code**: Install "D2" extension by Terrastruct, then `Cmd+Shift+P` -> "D2: Open Preview"

## When to Update

Update diagrams when:
- New component/service/extractor added
- Component relationships change
- Data flow changes
- Architecture patterns change

## D2 Quick Reference

### Layout Direction

```d2
# Vertical flow (default for main structure)
direction: down

# Horizontal flow (good for side-by-side components)
direction: right

# Per-container direction
my_container: {
  direction: right  # Override for this container only
}
```

### Containers

```d2
# Simple container
layer: "Layer Name" {
  component1: "Component 1"
  component2: "Component 2"
}

# Nested containers
outer: {
  inner: {
    item: "Item"
  }
}
```

### Connections

```d2
a -> b                    # Simple arrow
a -> b: "label"           # Labeled arrow
a <- b: "reverse"         # Reverse direction
a -> b -> c               # Chained

# Styled arrow
a -> b: "data" {
  style.stroke: "#F57C00"
  style.stroke-dash: 3    # Dashed line
  style.stroke-width: 2   # Thicker line
}
```

### Styling with Classes

```d2
# Define reusable classes
classes: {
  service: {
    style.fill: "#6ABF69"
    style.font-color: "#FFFFFF"
  }
  abstract: {
    style.stroke-dash: 5
    style.fill: "#E0E0E0"
  }
}

# Apply class
my_service: "ServiceName" { class: service }
my_base: "BaseClass" { class: abstract }
```

### Compact Labels

```d2
# Use pipe separators for lists
storage: "Supabase | LocalJson | S3" { class: infra }

# Use newlines for multi-line
component: "ComponentName\n(description)" { class: service }
```

## Reserved Keywords

**Avoid these as shape names** (will cause errors):
- `shadow` - use `shadow_mode` or `shadow_cmp` instead
- `style` - use `styling` instead
- `class` - use `cls` instead
- `label` - use `lbl` instead

## Layout Tips

### Vertical vs Horizontal

```d2
# Vertical: Good for showing flow/hierarchy
main_flow: {
  direction: down
  step1 -> step2 -> step3
}

# Horizontal: Good for parallel components
services: {
  direction: right
  profile: { direction: down; ... }
  feedback: { direction: down; ... }
  evaluation: { direction: down; ... }
}
```

### Making Diagrams Compact

1. **Use horizontal layout for groups**: `direction: right` for sibling containers
2. **Combine items with pipes**: `"A | B | C"` instead of separate boxes
3. **Shorten labels**: Remove bullet points, use abbreviations
4. **Reduce nesting**: Flatten where possible
5. **Remove redundant arrows**: Keep essential data flows only

### Example: Compact vs Verbose

```d2
# Verbose (takes more space)
storage: {
  supabase: "SupabaseStorage" { class: infra }
  local: "LocalJsonStorage" { class: infra }
  s3: "S3JsonStorage" { class: infra }
}

# Compact (single line)
storage: "Supabase | LocalJson | S3" { class: infra }
```

## Color Coding

| Color | Hex | Usage |
|-------|-----|-------|
| Blue | `#4A90D9` | API layer |
| Dark Blue | `#1565C0` | Orchestrators |
| Green | `#6ABF69` | Services |
| Light Green | `#8BC34A` | Extractors |
| Orange | `#FF9800` | Infrastructure |
| Gray | `#9E9E9E` | Config/Database |
| Purple | `#7E57C2` | State/Versioning |
| Yellow | `#FFF59D` | Data models |

## Adding Components

### New Extractor

1. Add to appropriate service in `service_layer_detail.d2`:
```d2
services.feedback: {
  new_ext: "NewExtractor" { class: extractor }
  svc -> new_ext: creates
}
```

2. Add storage connection:
```d2
services.feedback.new_ext -> storage.feedbacks: save {
  style.stroke: "#F57C00"
}
```

### New Service

1. Add service container:
```d2
services: {
  direction: right
  # ... existing services ...

  new_service: "NewService" {
    direction: down
    svc: "NewGenerationService" { class: service }
    ext: "NewExtractor" { class: extractor }
    svc -> ext
  }
}
```

2. Connect to orchestrator:
```d2
generation_service -> services.new_service.svc
```

3. Add base class extension:
```d2
base_service <- services.new_service.svc: extends
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Reserved keyword error | Rename shape (e.g., `shadow` → `shadow_mode`) |
| Diagram too wide | Use `direction: down` for main flow |
| Diagram too tall | Use `direction: right` for parallel components |
| Arrows overlapping | Reorder shapes in source, adjust container directions |
| Text too long | Use `\n` for line breaks, shorten descriptions |

## File Conventions

1. **Header comment**: Include render command
   ```d2
   # Component Architecture
   # Render: d2 file.d2 file.svg
   ```

2. **Section separators**: Use comment blocks
   ```d2
   # =============================================================================
   # SECTION NAME
   # =============================================================================
   ```

3. **Naming**: Use snake_case for shape IDs, match code structure

## Resources

- [D2 Documentation](https://d2lang.com/tour/intro)
- [D2 Playground](https://play.d2lang.com/)
- [D2 GitHub](https://github.com/terrastruct/d2)
