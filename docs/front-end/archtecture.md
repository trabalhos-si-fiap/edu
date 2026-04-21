# AI Coding Guidelines for Dart & Flutter Projects

This document serves as the master instruction set for AI-assisted development in this project. All code generated must adhere to these architectural standards to ensure maintainability and context-awareness.

## 1. Project Architecture: Feature-First
The project is organized by features, not by technical layers. Each feature folder should be self-contained.

### Structure:
```text
lib/
├── core/                   # Global shared resources
│   ├── network/            # API Clients (Dio/Http)
│   ├── theme/              # Styling, Colors, Typography
│   └── utils/              # Extension methods, Validators
├── features/               # Domain-specific modules
│   └── <feature_name>/     # Example: auth, dashboard, profile
│       ├── data/           # DTOs, Repositories, Data Sources
│       ├── domain/         # Entities, Use Cases (Pure Dart)
│       └── presentation/   # UI Widgets, Screens, State Management
└── main.dart

2. Coding Principles
Separation of Concerns

    UI is Dumb: Widgets should only handle rendering. Do not put business logic inside build() methods.

    Smart Logic: Business logic must reside in a State Management controller (e.g., Notifier, Bloc, or Controller).

    Inversion of Control: Use Constructor Injection for dependencies.

Naming Conventions

    Files: snake_case.dart.

    Classes: PascalCase.

    Variables/Methods: camelCase.

    Private members: Prefix with underscore _variableName.

3. State Management Standards

    Preferred Library: Flutter Riverpod (or specify your choice: Bloc, Provider, etc.).

    Logic Placement: Keep business logic inside Providers or StateNotifiers.

    Async Operations: Always use AsyncValue or equivalent patterns to handle Loading, Error, and Data states explicitly.

4. UI & Styling Rules

    No Global CSS: Use ThemeData defined in core/theme/ for app-wide styles.

    Composition over Inheritance: Wrap widgets (e.g., Padding, Center, SizedBox) instead of seeking layout properties within leaf widgets.

    Atomic Widgets: Break down complex screens into smaller, reusable private widgets within the same file or a widgets/ subfolder.

5. Error Handling & Functional Programming

    No Generic Throws: Use a Result or Either pattern for repository methods.

    Data Safety: Always handle nullability strictly using Dart's Sound Null Safety.

    API Responses: Map JSON to DTOs in the data/ layer before converting them to Domain Entities.

6. Development Workflow for AI

    Context Loading: Before writing a new feature, read the relevant folder in features/.

    Imports: Use Barrel Files (index.dart) in core/ and feature roots to minimize import noise.

    Refactoring: If a file exceeds 250 lines, suggest a refactoring strategy to split UI from Logic.
    """