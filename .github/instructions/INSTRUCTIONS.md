# INSTRUCTIONS.md

## Purpose

This document defines the mandatory architectural, development, scalability, maintenance, and documentation rules that all contributors (human or AI) must follow when working on this codebase.

The primary objective is:

> **The architecture must allow new features to be added with minimal impact on existing code by enforcing clear ownership, predictable dependencies, and reusable business logic.**

Every architectural decision must be evaluated against this principle.

---

# Core Architectural Philosophy

## Primary Rule

Before implementing any feature, refactor, optimization, or architectural change, always ask:

> "Will this make future features easier to add without modifying unrelated code?"

If a solution increases coupling, duplicates logic, introduces hidden dependencies, or requires modifying unrelated modules, it should be reconsidered.

---

# Scalability First Development Rule (SFDR)

The system must be designed so that:

* New features can be added with minimal modification to existing code.
* Existing functionality remains stable.
* Business logic remains reusable.
* Dependencies remain predictable.
* Ownership is clear.
* Modules remain easy to understand.
* Responsibilities remain well-defined.

Preferred outcome:

```text
Add Feature
    ↓
Create New Module
Create New Service
Create New Components
Minimal Changes Elsewhere
```

Avoid:

```text
Add Feature
    ↓
Modify 15 Existing Files
Copy Logic
Duplicate Validation
Duplicate Queries
Hidden Dependencies
```

---

# Domain Ownership Rule

Every module should own a single domain concern.

Examples:

```text
User Module
    ├── Create User
    ├── Update User
    ├── Delete User
    └── User Queries
```

These all belong to the User domain.

Avoid splitting responsibilities so aggressively that related functionality becomes difficult to discover.

---

# Architectural Layers

The architecture follows four primary layers:

```text
Interface Layer
        ↓
Application Layer
        ↓
Domain Layer
        ↓
Infrastructure Layer
```

---

# Layer Responsibilities

## Interface Layer

Examples:

* REST API
* Telegram Bot
* Web Application
* Admin Dashboard
* CLI
* Mobile Application

Responsibilities:

* Receive user input
* Return responses
* Authentication
* Request routing

Forbidden:

* Business logic
* Persistence logic
* External service orchestration

---

## Application Layer

Examples:

* UserService
* RequestService
* MatchingService
* NotificationService

Responsibilities:

* Feature orchestration
* Use cases
* Application workflows
* Coordination between modules

Answers:

> What should happen?

Forbidden:

* Database implementation details
* Framework-specific persistence logic

---

## Domain Layer

Contains:

* Business rules
* Policies
* Domain entities
* Domain value objects
* Core business behavior

Answers:

> Why does the business behave this way?

Business rules should live here whenever possible rather than becoming embedded inside large services.

---

## Infrastructure Layer

Contains:

* Database access
* Repositories
* External APIs
* Redis
* Queues
* Email providers
* File storage
* AI providers
* Logging
* Configuration

Answers:

> How is this implemented?

Infrastructure details should remain isolated from business logic.

---

# Dependency Rules

Dependencies must move inward toward business logic.

Allowed:

```text
Interface
    ↓
Application
    ↓
Domain
    ↓
Infrastructure
```

Application services may communicate with other application services when necessary.

Forbidden:

```text
Interface → Infrastructure

Interface → Database

Infrastructure → Application

Infrastructure → Domain Logic

Domain → Interface
```

---

# Feature Ownership Requirements

Every feature must explicitly define:

* Owner Module
* Entry Points
* Dependencies
* Business Rules
* Persistence Requirements
* External Integrations

Example:

```text
Notification Feature

Owner:
NotificationService

Entry Points:
REST API
Telegram Bot

Persistence:
Optional

External:
Email Provider
SMS Provider
```

If ownership is unclear, the feature is architecturally incomplete.

---

# Feature Development Workflow

## Step 1

Define feature requirements.

## Step 2

Identify:

* Owner Module
* Application Services
* Domain Rules
* Persistence Needs
* External Integrations

## Step 3

Update architecture documentation if architecture changes.

## Step 4

Implement the feature.

## Step 5

Add or update tests.

## Step 6

Update documentation if implementation changes architecture.

---

# Reusability Rule

Business logic must never belong to interfaces.

Bad:

```text
Telegram Handler
    ↓
Matching Logic
```

Good:

```text
Telegram Handler
    ↓
MatchingService
```

All interfaces should reuse shared application services.

Example:

```text
REST API
Telegram Bot
Dashboard
Mobile App

        ↓

MatchingService
```

One source of truth.

---

# Shared Components Rule

Reusable functionality should live in shared modules.

Examples:

```text
shared/
    ├── auth/
    ├── logging/
    ├── config/
    ├── caching/
    ├── utilities/
    └── http/
```

Shared modules must remain generic and reusable.

Business-specific logic must not be placed inside shared modules.

---

# Documentation Requirements

Create this file:

```text
docs/architecture.md
```

is the primary architectural reference.

It must accurately reflect the current architecture.

Documentation should focus on architectural decisions rather than implementation details.

---

# Mandatory architecture.md Sections

## System Overview

Must include:

* Purpose
* High-level architecture
* Dependency flow
* Data flow

---

## Module Overview

For each major module:

* Purpose
* Responsibilities
* Dependencies
* Extension guidelines

---

## Architecture Diagram

Must show:

```text
Interface
↓
Application
↓
Domain
↓
Infrastructure
```

and major module interactions.

---

## Feature Ownership Map

For each major feature:

* Owner Module
* Entry Points
* Dependencies
* Persistence Requirements
* External Integrations

---

## Extension Guide

Must explain:

* Adding features
* Modifying features
* Refactoring features
* Deprecating features

---

## Debugging Guide

Example:

```text
Input Validation Bug
→ Interface Layer

Workflow Bug
→ Application Layer

Business Rule Bug
→ Domain Layer

Database Bug
→ Infrastructure Layer

External API Bug
→ Infrastructure Layer
```

---

# Testing Requirements

Every feature should have appropriate test coverage.

Recommended:

```text
Application Layer
    → Unit Tests

Domain Layer
    → Unit Tests

Infrastructure Layer
    → Integration Tests

Critical Workflows
    → End-to-End Tests
```

Tests should validate behavior, not implementation details.

---

# Anti-Patterns

## Forbidden

Direct database access from interfaces:

```python
user = await db.fetch(...)
```

Preferred:

```python
user = await user_service.get_user(...)
```

---

## Forbidden

Large multi-purpose services:

```python
UserService:
    create_user()
    send_email()
    generate_jwt()
    query_database()
```

Preferred:

```python
UserService
AuthService
NotificationService
UserRepository
```

Each component should have clear ownership.

---

# Architecture Maintenance Rules

Whenever any of the following change:

* Major module structure
* Dependency flow
* Feature ownership
* Architectural boundaries
* Infrastructure integrations

The contributor must update:

```text
docs/architecture.md
```

within the same change.

Architecture documentation must not drift significantly from implementation.

---

# AI Agent Rules

The agent must:

* Follow architecture.md.
* Follow SFDR.
* Respect ownership boundaries.
* Reuse existing abstractions before creating new ones.
* Avoid duplication.
* Prevent hidden dependencies.
* Prevent architectural drift.
* Flag architectural violations.
* Request clarification when intent is unclear.
* Update architecture documentation when architecture changes.

The agent must never:

* Guess architectural intent.
* Introduce undocumented dependencies.
* Bypass architectural boundaries.
* Create duplicate abstractions without justification.
* Leave architecture documentation outdated.

---

# Success Criteria

The architecture is successful when:

* A new developer can understand the system quickly.
* New features can be added with minimal impact on existing code.
* Business logic has clear ownership.
* Dependencies remain predictable.
* Bugs can be traced through known architectural layers.
* New interfaces can be added without rewriting business logic.
* The codebase remains scalable, maintainable, consistent, and easy to extend.
