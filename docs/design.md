---
version: alpha
name: Kortex
description: AI Agent Orchestration Console and Fabric system interface design system.

colors:
  dark:
    background: "#090C15"
    surface: "#101423"
    on-background: "#E2E8F0"
    on-surface: "#94A3B8"
    primary: "#4FD1C5"
    on-primary: "#090C15"
    secondary: "#8FA1B3"
    border: "rgba(255, 255, 255, 0.05)"
    border-interactive: "rgba(79, 209, 197, 0.3)"
    error: "#F87171"
    success: "#34D399"
  light:
    background: "#F4F4F5"
    surface: "#FFFFFF"
    on-background: "#18181B"
    on-surface: "#52525B"
    primary: "#0D9488"
    on-primary: "#FFFFFF"
    secondary: "#4A6B82"
    border: "rgba(0, 0, 0, 0.06)"
    border-interactive: "rgba(13, 148, 136, 0.3)"
    error: "#EF4444"
    success: "#10B981"

typography:
  fontFamily-sans: "Inter, system-ui, sans-serif"
  fontFamily-brand: "Space Grotesk, sans-serif"
  fontFamily-mono: "IBM Plex Mono, monospace"
  h1:
    fontFamily: "{typography.fontFamily-brand}"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.2
  h2:
    fontFamily: "{typography.fontFamily-brand}"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.3
  h3:
    fontFamily: "{typography.fontFamily-brand}"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "{typography.fontFamily-sans}"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  caption:
    fontFamily: "{typography.fontFamily-sans}"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.4
  code:
    fontFamily: "{typography.fontFamily-mono}"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.4
  logo:
    fontFamily: "{typography.fontFamily-brand}"
    fontSize: "1.75rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.08em"

rounded:
  none: "0px"
  xs: "2px"
  sm: "4px"
  md: "8px"

spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"

components:
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
    border: "1px solid {colors.border}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.xs}"
    padding: "{spacing.sm} {spacing.md}"
    typography: "{typography.code}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.secondary}"
    rounded: "{rounded.xs}"
    padding: "{spacing.sm} {spacing.md}"
    border: "1px solid {colors.border}"
    typography: "{typography.code}"
  input:
    backgroundColor: "rgba(0, 0, 0, 0.03)"
    textColor: "{colors.on-background}"
    rounded: "{rounded.xs}"
    padding: "{spacing.sm} {spacing.md}"
    border: "1px solid {colors.border}"
    typography: "{typography.body}"
---

# Kortex Design System

## Overview
Kortex is an advanced AI agent orchestration console. Its design system, **AI Fabric Console**, merges the structural complexity of a technical command HUD with a highly focused, modern visual interface. Kortex uses a strict grid layout, hairline boundaries, and technical data nodes to convey total process control, while maintaining visual comfort through low-saturation colors and low-contrast details. The goal is to provide a highly professional engineering environment that eliminates cognitive noise and visual fatigue over continuous hours of work.

## Colors
The system relies on a dual-mode strategy utilizing low-saturation, high-comfort palettes:
- **Dark Mode (Default):** Anchored on a deep, obsidian slate-blue background (`#090C15`) that minimizes eye glare in low light. Primary highlights use soft brushed teal (`#4FD1C5`) and muted glacial-blue (`#8FA1B3`) for structural telemetry.
- **Light Mode:** Anchored on a matte bone/parchment off-white (`#F4F4F5`) that mimics solid industrial hardware and provides comfortable reading contrast without bright white glares.
- **Contrast & Hierarchy:** Alerts (`success` and `error`) use soft, non-emissive tones. Active states are emphasized with thin border glows using `{colors.border-interactive}` rather than heavy solid blocks.

## Typography
Kortex uses a clean typography mix that balances brand authority with technical precision:
- **Space Grotesk:** Applied to logo wordmarks, headings (`h1`, `h2`, `h3`), and technical dashboard section headers. Large titles feature expanded letter spacing (`letter-spacing: 0.08em`) to convey a modern, premium stark feel.
- **IBM Plex Mono:** Employed for all numerical outputs, telemetry readouts, status tables, code scripts, and logs. It ensures clear symbol distinction and vertical readability of tabular data.
- **Inter:** The default sans-serif font for tooltips, logs, parameter controls, settings lists, and description copy, providing maximum reading flow.

## Layout
The interface is structured as a strict grid layout, separating data panels with 1px hairline borders (`{colors.border}`). 
- **Grids & Hairlines:** The visual structure relies on cards with clean, thin outlines. Subtle crosshair decorators (`+`) are positioned at grid intersections to evoke a high-precision measurement workspace.
- **Spacing Scale:** Built on a strict 8px grid. Density is comfortable but compact, ensuring high-density metrics are easily readable without overlapping.
- **Translucency:** Glassmorphism is used strategically using `backdrop-filter: blur(12px)` for overlay menus and drawer panels.

## Elevation & Depth
In a flat, high-tech grid system, physical drop shadows are minimized. Depth is communicated structurally:
- **Layer 0 (Background):** Base canvas (`{colors.background}`). Includes low-opacity grid lines.
- **Layer 1 (Panels):** Interactive cards (`{colors.surface}`) delimited by thin hairlines.
- **Layer 2 (Overlays):** Translucent overlays (`backdrop-filter`) with subtle `rgba` border lines.
- **Interaction Depth:** Hover states on interactive cards do not pop out with shadows. Instead, they shift borders to `{colors.border-interactive}` or light up metadata texts.

## Shapes
Kortex uses a clean and structured shape language inspired by premium hardware:
- **Sharp/Semi-Sharp Corners:** Corner rounding is kept minimal to emphasize structure.
  - Buttons, inputs, and minor widgets use `{rounded.xs}` (2px) to look precise and technical.
  - Standard cards and control panels use `{rounded.sm}` (4px) to retain structural boundaries.
  - No circles or fully rounded chips are used unless they are status indicators or radar displays.

## Components
All Kortex interface elements reference design tokens:
- **Cards:** Delimited by a thin 1px border. Feature a gold/teal header title followed by monospace telemetry widgets or graph nodes.
- **Interactive Nodes:** Used in AI agent graphs. Features a `{rounded.sm}` container with a `{colors.border}` outline, turning into `{colors.border-interactive}` when hovered or active.
- **Primary Buttons:** Muted color container with dark contrasting text, designed for execution triggers.
- **Secondary Buttons:** Completely flat with border lines, designed to keep visual hierarchy low.
- **Status Badges:** Small circular indicator lights displaying green (`{colors.success}`) or red (`{colors.error}`).

## Do's and Don'ts
- **DO:** Render all grid boundaries, graphs, and radar indicators with thin 1px lines (`rgba(255,255,255,0.05)`).
- **DO:** Use IBM Plex Mono for all tabular statistics, times, latency reports, and status numbers.
- **DO:** Apply Space Grotesk to section titles with uppercase treatment and spacing.
- **DO:** Keep border highlights low-saturation, ensuring alert colors are reserved exclusively for actual warnings/errors.
- **DON'T:** Use bright, glowing neon drop shadows or glow effects that create a halo bloom.
- **DON'T:** Design layouts without grid alignment. Every card must align cleanly with the underlying column framework.
- **DON'T:** Use rounded pills (`radius: 9999px`) or large corner roundings for primary interactive elements.
- **DON'T:** Add decorative visual noise (fake numbers, radar sweeps) that doesn't correspond to real application telemetry.
