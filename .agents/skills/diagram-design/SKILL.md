---
name: diagram-design
description: >-
  Generate clean, publication-grade editorial HTML and SVG architecture diagrams,
  system workflows, and sequence flows. Use this skill when the user asks for diagrams,
  flowcharts, architecture maps, or visual design overviews without low-fidelity styling.
---

# Diagram Design Skill

Inspired by [`cathrynlavery/diagram-design`](https://github.com/cathrynlavery/diagram-design), this skill guides the agent in generating clean, high-aesthetic, editorial system diagrams using self-contained HTML and inline SVG.

## Why Editorial Diagrams?

Default ASCII and basic Mermaid charts frequently suffer from poor text wrapping, rigid layouts, and lack of visual hierarchy. Editorial HTML/SVG diagrams provide:
- Custom typography (Inter, Roboto, sans-serif) and precise 1px borders.
- Crisp vector arrows and semantic color accents (slate, emerald, violet, amber).
- Interactive hover effects and responsive layout containers.
- Zero external build tooling: runs directly in any browser or webview.

---

## When to Use

- Visualizing multi-tier software architectures (Frontend ➔ API Gateway ➔ Microservices ➔ DB).
- Illustrating multi-agent execution loops and orchestration pipelines.
- Documenting request/response sequences or cryptographic handshake flows.
- Creating visual technical documentation for RFCs or READMEs.

---

## Design Principles

1. **Clean Monochrome with Intentional Color**: Use neutral canvas (`#0f172a` dark or `#ffffff` light) and reserve vibrant accents only for data flows, active agents, or critical bottlenecks.
2. **Generous Spacing & Hierarchy**: 16px to 24px padding within boxes, subtle corner radius (8px - 12px), clear titles with uppercase tracking.
3. **No Heavy Dropshadows**: Rely on crisp 1px borders (`border: 1px solid rgba(255,255,255,0.1)`) and flat contrast.
4. **Self-Contained Output**: Deliver the diagram in a single standalone `.html` file inside `diagrams/` or the conversation artifacts folder.

---

## Template Structure

When generating a diagram, adapt the template from `resources/template.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Architecture Diagram</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #090d16; color: #f8fafc; padding: 40px; display: flex; justify-content: center; }
    .canvas { width: 100%; max-width: 900px; display: flex; flex-direction: column; gap: 24px; }
    .card { background: #131b2e; border: 1px solid #1e293b; border-radius: 10px; padding: 20px; }
    .badge { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; padding: 4px 8px; border-radius: 4px; }
  </style>
</head>
<body>
  <!-- Diagram Layout with SVG Connectors -->
</body>
</html>
```
