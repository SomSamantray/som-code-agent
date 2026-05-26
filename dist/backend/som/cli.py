#!/usr/bin/env python3
"""
Som CLI — Your coding agent harness.

Usage:
    som "Build a REST API"              # Interactive coding session
    som run "Fix the tests"             # Explicit coding session
    som plan "Design auth system"       # Plan → approve → execute
    som chat "Explain decorators"       # Simple conversation
    som exec "Write a script"           # Non-interactive execution
    som config                          # View/edit configuration
    som skills [--search QUERY]         # Manage skills
    som history [--limit N]             # Session history
    som resume [SESSION_ID]             # Resume a session
    som init                            # Initialize SOM.md
    som compare A B "task"              # Compare two models

Global flags:
    --model, -m      Model spec (e.g., openrouter/anthropic/claude-sonnet-4)
    --workspace, -w  Working directory
    --permission, -p Permission mode (default, acceptEdits, plan, bypass)
    --max-turns      Max turns (default: 50)
    --temperature    Model temperature (default: 0.3)
    --effort         Reasoning effort (low, medium, high, max)
    --config         Config file path
    --verbose, -v    Verbose output
    --dangerously-skip-permissions  YOLO mode
"""

import argparse
import os
import sys
import json
import time
from pathlib import Path

# Add parent to path
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _parent)

from harness.providers import ProviderClient, resolve_provider
from harness.sandbox import SubprocessSandbox
from harness.skills import get_skill_loader, SkillLoader
from harness.core import CodingHarness
from harness.hooks import HookSystem, create_path_protection_hook, create_destructive_command_hook

from som.tools.all_tools import create_som_tools
from som.agent.plan import PlanModeManager, READ_ONLY_TOOLS
from som.agent.compact import ContextCompactor
from som.context.som_md import SomConfigLoader
from som.session.history import SessionManager


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _print_banner():
    """Print Som CLI banner."""
    print("""
╔══════════════════════════════════╗
║       🧠 Som CLI v2.0           ║
║  Your Coding Agent Harness       ║
╚══════════════════════════════════╝
""")

def _resolve_model(args) -> str:
    """Resolve model from args, env, or config."""
    if hasattr(args, 'model') and args.model:
        return args.model
    # Check env
    for env_var in ['SOM_MODEL', 'OPENROUTER_MODEL']:
        if os.environ.get(env_var):
            return os.environ[env_var]
    # Default
    provider = os.environ.get('OPENROUTER_API_KEY') and 'openrouter' or 'ollama'
    if provider == 'openrouter':
        return 'openrouter/anthropic/claude-sonnet-4'
    return 'ollama/qwen2.5:7b'

def _resolve_workspace(args) -> str:
    """Resolve workspace from args or cwd."""
    if hasattr(args, 'workspace') and args.workspace:
        return os.path.abspath(args.workspace)
    return os.path.join(os.getcwd(), '.som_workspace')

def _print_turn(turn_idx: int, content: str = "", tool_name: str = "", tool_status: str = ""):
    """Pretty-print a turn."""
    if tool_name:
        icon = "✅" if "success" in tool_status.lower() else "⚠️"
        print(f"  {icon} [{turn_idx}] {tool_name}: {tool_status[:80]}")
    elif content:
        print(f"\n💬 [{turn_idx}] {content[:200]}")

def _interactive_clarify(questions: list[dict]) -> dict:
    """Handle interactive AskUserQuestion in the CLI."""
    answers = {}
    
    for i, q in enumerate(questions):
        print(f"\n{'='*50}")
        print(f"❓ {q.get('header', f'Question {i+1}')}")
        print(f"   {q['question']}")
        print()
        
        options = q.get('options', [])
        for j, opt in enumerate(options, 1):
            print(f"  {j}. {opt['label']} — {opt.get('description', '')}")
        print(f"  {len(options) + 1}. Other (type your answer)")
        print()
        
        multi = q.get('multiSelect', False)
        prompt = f"  Choose (1-{len(options) + 1}{', comma-separated for multi-select' if multi else ''}): "
        
        while True:
            try:
                choice = input(prompt).strip()
                
                if not choice:
                    continue
                
                if multi:
                    # Parse comma-separated choices
                    selected = [c.strip() for c in choice.split(',')]
                    selected_labels = []
                    for c in selected:
                        try:
                            idx = int(c) - 1
                            if 0 <= idx < len(options):
                                selected_labels.append(options[idx]['label'])
                            elif idx == len(options):
                                # "Other" option
                                other = input("  Type your answer: ").strip()
                                selected_labels.append(other)
                            else:
                                print(f"  Invalid choice: {c}")
                                continue
                        except ValueError:
                            selected_labels.append(c)  # Treat as free text
                    answers[q['question']] = selected_labels
                else:
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(options):
                            answers[q['question']] = options[idx]['label']
                        elif idx == len(options):
                            other = input("  Type your answer: ").strip()
                            answers[q['question']] = other
                        else:
                            print(f"  Please enter 1-{len(options) + 1}")
                            continue
                    except ValueError:
                        answers[q['question']] = choice  # Free text
                break
            except (KeyboardInterrupt, EOFError):
                print("\n  Cancelled.")
                return {}
    
    return answers


# ═══════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════

def cmd_run(args):
    """Run a coding task with the full agent harness."""
    model = _resolve_model(args)
    workspace = _resolve_workspace(args)
    permission = getattr(args, 'permission', 'default')
    
    # Load SOM.md context
    som_loader = SomConfigLoader(project_root=workspace)
    som_context = som_loader.get_system_prompt_block()
    
    print(f"🤖 Model: {model}")
    print(f"📁 Workspace: {workspace}")
    print(f"🔒 Permission: {permission}")
    print(f"📋 Task: {args.task}\n")
    
    sandbox = SubprocessSandbox(workspace=workspace)
    
    # Build custom system prompt with SOM.md
    system_prompt = None
    if som_context:
        system_prompt = f"""You are Som, a coding agent. Complete coding tasks by using the tools available.

{som_context}

## How to Work
1. Understand the user's request
2. Plan your approach using todo_write
3. Use tools to explore, write, and test code
4. Verify your work
5. Call task_complete when finished

## Rules
- Execute one step at a time
- Read files before editing them
- Test your code after writing it
- If a tool fails, read the error and try a different approach
- Use grep and glob to understand the codebase before making changes
- Use ask_user_question when you need clarification
- If a skill matches your task, load it with skill_view(name) before proceeding
"""
    
    # Set up hooks
    hooks = HookSystem()
    hooks.register("before_tool_exec", create_path_protection_hook(workspace))
    hooks.register("after_tool_exec", create_destructive_command_hook())
    
    # Handle tool blocking for plan mode
    if permission == "plan":
        def plan_mode_block(ctx):
            from som.agent.plan import READ_ONLY_TOOLS
            tool_name = ctx.data.get("tool_name", "")
            if tool_name not in READ_ONLY_TOOLS:
                ctx.blocked = True
                ctx.block_reason = f"Tool '{tool_name}' is not allowed in plan mode. Only read/search tools are permitted."
            return ctx
        hooks.register("before_tool_exec", plan_mode_block)
    
    # Create agent with Som tools
    harness = CodingHarness(
        model,
        tools=create_som_tools(sandbox),
        hooks=hooks,
        system_prompt=system_prompt,
        max_turns=getattr(args, 'max_turns', 50),
    )
    
    # Session tracking
    session_mgr = SessionManager()
    session = session_mgr.start_session(args.task, model, workspace)
    
    t0 = time.time()
    
    try:
        result = harness.run(args.task, sandbox, max_turns=getattr(args, 'max_turns', 50))
        elapsed = time.time() - t0
        
        # Check for interactive questions
        interactive_questions = []
        for turn in result.turns:
            for tr in turn.tool_results:
                if hasattr(tr, 'metadata') and tr.metadata.get('interactive'):
                    questions = tr.metadata.get('questions', [])
                    answers = _interactive_clarify(questions)
                    # Answers would need to be fed back to agent in a full implementation
                    interactive_questions.append((questions, answers))
        
        print(f"\n{'='*60}")
        print(f"{'✅ COMPLETED' if result.success else '⚠️ FINISHED'} in {elapsed:.1f}s")
        print(f"   Turns: {len(result.turns)}")
        print(f"   Tool calls: {result.total_tool_calls}")
        print(f"   Repairs: {result.total_repairs}")
        if result.total_tokens.get("total"):
            print(f"   Tokens: {result.total_tokens['total']}")
        if result.error:
            print(f"   ❌ Error: {result.error}")
        
        print(f"\n📝 Final response:\n{result.final_response}")
        
        # End session
        session_mgr.end_session(
            success=result.success,
            final_response=result.final_response,
            error=result.error,
        )
        
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user.")
        session_mgr.end_session(success=False, error="Interrupted")
    finally:
        sandbox.cleanup()


def cmd_plan(args):
    """Plan mode: research → plan → approve → execute."""
    model = _resolve_model(args)
    workspace = _resolve_workspace(args)
    
    print(f"📋 Plan Mode — {model}")
    print(f"📁 Workspace: {workspace}")
    print(f"📋 Task: {args.task}\n")
    
    plan_mgr = PlanModeManager()
    print(plan_mgr.enter())
    print()
    
    # Phase 1: Research (read-only agent run)
    sandbox = SubprocessSandbox(workspace=workspace)
    som_loader = SomConfigLoader(project_root=workspace)
    som_context = som_loader.get_system_prompt_block()
    
    system_prompt = f"""You are Som in PLAN MODE. Your job is to research and create a detailed implementation plan.

{som_context if som_context else ''}

## PLAN MODE RULES
You have READ-ONLY access. You CAN:
- Read files, search code (grep, glob), browse the web
- Ask clarifying questions via ask_user_question
- Explore project structure

You CANNOT:
- Write or edit files
- Run shell commands that modify anything

## Your Job
1. Research the codebase and understand the current state
2. Ask clarifying questions for any ambiguities
3. Design the architecture and approach
4. Present a structured plan containing:
   - What to build (components, files)
   - Architecture decisions
   - Implementation order (step by step)
   - Testing strategy
   - Risks and alternatives

When ready, call exit_plan_mode(your_plan) to present your plan.
"""
    
    harness = CodingHarness(
        model,
        tools=create_som_tools(sandbox),
        system_prompt=system_prompt,
        max_turns=30,
    )
    
    t0 = time.time()
    result = harness.run(args.task, sandbox, max_turns=30)
    elapsed = time.time() - t0
    
    # Check for plan exit
    plan_text = None
    for turn in result.turns:
        for tr in turn.tool_results:
            if hasattr(tr, 'metadata') and tr.metadata.get('plan_exit'):
                plan_text = tr.metadata.get('plan', '')
    
    if plan_text:
        print(PlanModeManager.format_approval_prompt(plan_text))
        print()
        
        # Get user approval
        try:
            choice = input("  Your choice (1-4): ").strip()
        except (KeyboardInterrupt, EOFError):
            choice = "4"
        
        approval_map = {
            "1": ("approve_execute", True, "execute"),
            "2": ("approve_review", True, "review"),
            "3": ("refine", False, "refine"),
            "4": ("save", True, "save"),
        }
        
        action, approved, mode = approval_map.get(choice, ("save", True, "save"))
        
        if mode == "refine":
            feedback = input("  What should be changed? ").strip()
            print(f"\n  Feedback recorded: {feedback}")
            print("  Run 'som plan' again with your feedback to refine the plan.")
        elif mode == "save":
            path = plan_mgr._save_plan()
            print(f"\n  Plan saved to {path}")
        elif approved:
            print(plan_mgr.exit(approved=True, mode=mode))
            if mode == "execute":
                print("\n  Starting execution...\n")
                # Re-run in execute mode
                exec_args = argparse.Namespace(
                    task=args.task,
                    model=model,
                    workspace=workspace,
                    permission='default',
                    max_turns=getattr(args, 'max_turns', 50),
                )
                cmd_run(exec_args)
    else:
        print(f"\n⚠️ Plan mode completed without presenting a plan.")
        print(f"   Final response: {result.final_response[:500]}")
    
    sandbox.cleanup()


def cmd_chat(args):
    """Simple chat without sandbox."""
    model = _resolve_model(args)
    
    print(f"💬 Chat: {model}")
    print(f"   You: {args.message}\n")
    
    client = ProviderClient(model)
    messages = []
    
    if hasattr(args, 'system') and args.system:
        messages.append({"role": "system", "content": args.system})
    
    messages.append({"role": "user", "content": args.message})
    
    t0 = time.time()
    response = client.chat(
        messages,
        temperature=getattr(args, 'temperature', 0.7),
        max_tokens=getattr(args, 'max_tokens', 4096),
    )
    elapsed = time.time() - t0
    
    content = response.choices[0].message.content or "(empty response)"
    
    print(f"\n🤖 Assistant ({elapsed:.1f}s):")
    print(content)


def cmd_exec(args):
    """Non-interactive execution — similar to 'codex exec'."""
    model = _resolve_model(args)
    workspace = _resolve_workspace(args)
    
    sandbox = SubprocessSandbox(workspace=workspace)
    
    harness = CodingHarness(
        model,
        tools=create_som_tools(sandbox),
        max_turns=getattr(args, 'max_turns', 30),
    )
    
    t0 = time.time()
    result = harness.run(args.task, sandbox)
    elapsed = time.time() - t0
    
    # Machine-readable output
    if getattr(args, 'json', False):
        print(json.dumps({
            "success": result.success,
            "turns": len(result.turns),
            "tool_calls": result.total_tool_calls,
            "elapsed": round(elapsed, 2),
            "response": result.final_response,
            "error": result.error,
        }, indent=2))
    else:
        print(result.final_response)
        if not result.success:
            print(f"\n⚠️ Error: {result.error}", file=sys.stderr)
            sys.exit(1)
    
    sandbox.cleanup()


def cmd_compare(args):
    """Compare two models on the same task."""
    print(f"🔬 Comparing: {args.model_a} vs {args.model_b}")
    print(f"📋 Task: {args.task}\n")
    
    results = {}
    
    for model_spec in [args.model_a, args.model_b]:
        workspace = os.path.join(os.getcwd(), f".som_compare_{model_spec.replace('/', '_')}")
        sandbox = SubprocessSandbox(workspace=workspace)
        
        print(f"⏳ Running {model_spec}...")
        harness = CodingHarness(model_spec, tools=create_som_tools(sandbox), max_turns=30)
        t0 = time.time()
        result = harness.run(args.task, sandbox)
        elapsed = time.time() - t0
        
        results[model_spec] = {
            "success": result.success,
            "turns": len(result.turns),
            "tool_calls": result.total_tool_calls,
            "elapsed": elapsed,
            "tokens": result.total_tokens,
        }
        
        print(f"   {'✅' if result.success else '⏹'} {model_spec}")
        print(f"   Time: {elapsed:.1f}s | Turns: {len(result.turns)} | Tools: {result.total_tool_calls}")
        sandbox.cleanup()
    
    print(f"\n{'='*50}")
    print("COMPARISON SUMMARY:")
    for model, data in results.items():
        print(f"  {model}:")
        print(f"    Success: {data['success']} | Turns: {data['turns']} | Time: {data['elapsed']:.1f}s")


def cmd_config(args):
    """View or edit Som configuration."""
    project_root = getattr(args, 'workspace', None) or os.getcwd()
    som_loader = SomConfigLoader(project_root=project_root)
    
    config = som_loader.discover()
    
    if not config:
        print("No SOM.md found. Run 'som init' to create one.")
        return
    
    print(f"📋 SOM.md ({config.level}): {config.path}")
    if config.imports:
        print(f"   Imports: {', '.join(config.imports)}")
    print(f"\n{config.content[:2000]}")
    if len(config.content) > 2000:
        print(f"\n... ({len(config.content)} chars total)")


def cmd_init(args):
    """Initialize a new SOM.md in the current project."""
    project_root = getattr(args, 'workspace', None) or os.getcwd()
    result = SomConfigLoader.init(project_root)
    print(result)


def cmd_skills(args):
    """List, search, or view skills."""
    loader = get_skill_loader()
    loader.discover()
    
    if hasattr(args, 'view') and args.view:
        skill = loader.get(args.view)
        if skill:
            print(f"# {skill.name} (v{skill.version})")
            print(f"  Category: {skill.category or 'root'}")
            print()
            print(skill.body)
        else:
            print(f"Skill '{args.view}' not found.")
    elif hasattr(args, 'search') and args.search:
        results = loader.search(args.search)
        print(f"Search: '{args.search}' → {len(results)} found\n")
        for s in results:
            print(f"  • {s.name} — {s.description}")
    else:
        skills = loader.list_all()
        print(f"Available skills ({len(skills)}):\n")
        for s in skills:
            cat = f"[{s.category}]" if s.category else ""
            print(f"  • {s.name} {cat}: {s.description}")


def cmd_history(args):
    """View session history."""
    session_mgr = SessionManager()
    
    limit = getattr(args, 'limit', 20)
    sessions = session_mgr.list_sessions(limit=limit)
    
    print(session_mgr.format_session_list(sessions))
    print(f"\nSessions stored in: ~/.som/sessions/")


def cmd_resume(args):
    """Resume a previous session."""
    session_mgr = SessionManager()
    
    if not args.session_id:
        # Show recent sessions to pick from
        sessions = session_mgr.list_sessions(limit=10)
        print(session_mgr.format_session_list(sessions))
        if sessions:
            print("\nRun: som resume <session_id>")
        return
    
    session = session_mgr.get_session(args.session_id)
    if not session:
        print(f"Session '{args.session_id}' not found.")
        return
    
    print(f"📋 Resuming: [{session.session_id}] {session.task}")
    print(f"   Model: {session.model} | Turns: {session.turn_count}")
    print(f"   Started: {session.started_at}")
    print(f"\n⚠️ Full context resume requires session transcript support (coming in v2.1).")
    print(f"   For now, re-running the original task:")
    print(f"   som run \"{session.task}\" --model {session.model}")


# ═══════════════════════════════════════════════════════════════════
# MAIN CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        prog="som",
        description="Som CLI — Your coding agent harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  som "Build a REST API with FastAPI"
  som run "Write tests for src/utils.py" --model openrouter/anthropic/claude-sonnet-4
  som plan "Design the authentication system"
  som chat "Explain how asyncio works"
  som exec "Generate a CSV parser" --json
  som skills --search python
  som history
  som init
  som config

Environment:
  OPENROUTER_API_KEY     OpenRouter API key (for openrouter provider)
  OPENAI_API_KEY         OpenAI API key
  ANTHROPIC_API_KEY      Anthropic API key
  DEEPSEEK_API_KEY       DeepSeek API key
  SOM_MODEL              Default model spec
""",
    )
    
    # Global flags
    parser.add_argument("--model", "-m", help="Provider/model spec")
    parser.add_argument("--workspace", "-w", help="Working directory")
    parser.add_argument("--permission", "-p", default="default",
                       choices=["default", "acceptEdits", "plan", "bypass"],
                       help="Permission mode")
    parser.add_argument("--max-turns", type=int, default=50, help="Max agent turns")
    parser.add_argument("--temperature", type=float, default=0.3, help="Model temperature")
    parser.add_argument("--effort", choices=["low", "medium", "high", "max"],
                       help="Reasoning effort")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--dangerously-skip-permissions", action="store_true",
                       help="Bypass all permission checks (use with caution)")
    
    sub = parser.add_subparsers(dest="command")
    
    # ── run (explicit) ──
    run_p = sub.add_parser("run", help="Run a coding task")
    run_p.add_argument("task", help="The coding task")
    
    # ── plan ──
    plan_p = sub.add_parser("plan", help="Plan mode: research → plan → approve")
    plan_p.add_argument("task", help="Task to plan for")
    
    # ── chat ──
    chat_p = sub.add_parser("chat", help="Simple conversation")
    chat_p.add_argument("message", help="Your message")
    chat_p.add_argument("--system", help="System prompt")
    chat_p.add_argument("--max-tokens", type=int, default=4096)
    
    # ── exec (non-interactive) ──
    exec_p = sub.add_parser("exec", help="Non-interactive execution")
    exec_p.add_argument("task", help="The coding task")
    exec_p.add_argument("--json", action="store_true", help="JSON output")
    
    # ── compare ──
    comp_p = sub.add_parser("compare", help="Compare two models")
    comp_p.add_argument("model_a", help="First model")
    comp_p.add_argument("model_b", help="Second model")
    comp_p.add_argument("task", help="The coding task")
    
    # ── config ──
    config_p = sub.add_parser("config", help="View SOM.md configuration")
    config_p.add_argument("--workspace", "-w", help="Project directory")
    
    # ── init ──
    init_p = sub.add_parser("init", help="Initialize SOM.md in project")
    init_p.add_argument("--workspace", "-w", help="Project directory")
    
    # ── skills ──
    skill_p = sub.add_parser("skills", help="List/search/view skills")
    skill_p.add_argument("--search", help="Search skills by keyword")
    skill_p.add_argument("--view", help="View a specific skill")
    
    # ── history ──
    hist_p = sub.add_parser("history", help="Session history")
    hist_p.add_argument("--limit", "-n", type=int, default=20)
    
    # ── resume ──
    res_p = sub.add_parser("resume", help="Resume a session")
    res_p.add_argument("session_id", nargs="?", help="Session ID to resume")
    
    args = parser.parse_args()
    
    # Dispatch
    if args.command == "run":
        cmd_run(args)
    elif args.command == "plan":
        cmd_plan(args)
    elif args.command == "chat":
        cmd_chat(args)
    elif args.command == "exec":
        cmd_exec(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "config":
        cmd_config(args)
    elif args.command == "init":
        cmd_init(args)
    elif args.command == "skills":
        cmd_skills(args)
    elif args.command == "history":
        cmd_history(args)
    elif args.command == "resume":
        cmd_resume(args)
    elif args.command is None:
        # Default: if args passed as positional, treat as run
        # Allow: som "task"  (without subcommand)
        import sys
        remaining = [a for a in sys.argv[1:] if not a.startswith('-')]
        if remaining:
            # Treat first positional as a task for 'run'
            args.task = remaining[0]
            args.command = "run"
            cmd_run(args)
        else:
            parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
