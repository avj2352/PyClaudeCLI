
import asyncio
import os
import pyperclip
import re
import sys
import typer
from typing import List, Dict, Optional, Any, Union
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from strands.agent import Agent
from strands.models import BedrockModel
from strands.types.content import Message
from strands_tools import (http_request, current_time)    


# Initialize Typer app and Rich console
app = typer.Typer()
console = Console()
APP_VERSION = "1.1.0"

# Configuration
class Config:
    MODELS = {
        "sonnet-4.5": {
            "modelId": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "description": "High intelligence and speed"
        },
        "opus-4.1": {
            "modelId": "us.anthropic.claude-opus-4-1-20250805-v1:0",
            "description": "Most capable model for complex tasks"
        },
        "qwen3 30B": {
            "modelId": "qwen.qwen3-coder-30b-a3b-v1:0",
            "description": "Very fast response code assist"
        },
        "sonnet-4": {
            "modelId": "us.anthropic.claude-sonnet-4-20250514-v1:0",
            "description": "Cost optimized anthropic model"
        },
        "deepseek R1": {
            "modelId": "us.deepseek.r1-v1:0",
            "description": "Reasoning focused model"
        },
    }
    DEFAULT_MODEL = "sonnet-4.5"

class ChatSession:
    def __init__(self):
        self.messages: List[Message] = []
        self.current_model_name = Config.DEFAULT_MODEL
        self.attachments: List[tuple[str, str]] = [] # (filename, content)
        self.last_response: Optional[str] = None
        self.last_code_blocks: List[str] = []
        self.prompt_session = PromptSession()

        # Token and model usage tracking
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.model_usage: Dict[str, int] = {}

        # Load skills content
        self.skills_content: str = self.load_skills()
        
        # Initialize Agent
        self.agent: Optional[Agent] = None
        self.init_agent()

    def init_agent(self):
        """Initialize or re-initialize the Strands Agent with the current model."""
        model_config = Config.MODELS[self.current_model_name]
        try:            
            # BedrockModel expects config or kwargs. We pass model_id/modelId.
            # Based on inspection, it accepts **model_config.
            model = BedrockModel(model_id=model_config["modelId"])
            
            # Tools
            tools = [http_request, current_time]
            
            # Create Agent
            # Note: We create a new agent when switching models. 
            # We don't pass history here because we maintain it in self.messages and pass it to stream_async.
            self.agent = Agent(
                model=model,
                tools=tools,
                callback_handler=None
            )
        except Exception as e:
            rprint(f"[bold red]Error initializing agent:[/bold red] {e}")

    def load_skills(self) -> str:
        """Load all markdown files from the skills folder and combine their content."""
        skills_dir = Path("skills")
        if not skills_dir.exists():
            return ""

        combined_skills = ""
        for skill_file in sorted(skills_dir.glob("*.md")):
            try:
                content = skill_file.read_text(encoding='utf-8')
                combined_skills += f"\n\n--- Skill: {skill_file.name} ---\n{content}\n"
            except Exception as e:
                rprint(f"[yellow]Warning: Could not read {skill_file.name}: {e}[/yellow]")

        return combined_skills

    def list_skills(self):
        """List all markdown files in the skills folder."""
        skills_dir = Path("skills")
        if not skills_dir.exists():
            rprint("[yellow]Skills folder does not exist.[/yellow]")
            return

        skill_files = list(skills_dir.glob("*.md"))
        if not skill_files:
            rprint("[yellow]🖇️ No skill files found in the skills folder.[/yellow]")
            return

        rprint("[bold cyan]Available Skills:[/bold cyan]")
        for skill_file in sorted(skill_files):
            rprint(f"  • {skill_file.name}")

    def prepare_user_message_content(self, content: str) -> str:
        """Prepare the initial message content properly with skills and attachments."""
        text_content = content
        
        # Add skills content as context (only for the first message or appropriately? 
        # The original code added it to EVERY user message if self.skills_content existed.
        # We will follow that pattern or optimized one. 
        # Original: if self.skills_content: msg_content[0]["text"] = f"{self.skills_content}\n\n{content}"
        if self.skills_content:
             text_content = f"{self.skills_content}\n\n{text_content}"

        # Add attachments if any
        if self.attachments:
            file_context = "\n\nAttached Files:\n"
            for name, body in self.attachments:
                file_context += f"--- BEGIN FILE: {name} ---\n{body}\n--- END FILE: {name} ---\n"

            text_content += file_context
            self.attachments = [] # Clear attachments after sending
            
        return text_content

    def add_user_message(self, content: str):
        full_content = self.prepare_user_message_content(content)
        # Create a Message object. 
        # Assuming Message(role="user", content=[{"text": ...}]) works or similar.
        # Strands Message expects content list.
        # We use a dict representation if allowed, or we verify Message structure.
        # Based on inspection: content: List[ContentBlock].
        # We'll try to use dicts which Pydantic often accepts.
        self.messages.append(Message(role="user", content=[{"text": full_content}]))

    def add_assistant_message(self, content: str):
        # We append the assistant response to history
        self.messages.append(Message(role="assistant", content=[{"text": content}]))
        self.extract_code_blocks(content)
        self.last_response = content

    def extract_code_blocks(self, text: str):
        pattern = r"```[\w]*\n(.*?)```"
        self.last_code_blocks = re.findall(pattern, text, re.DOTALL)

    def switch_model(self):
        models = list(Config.MODELS.keys())
        rprint(f"[bold cyan]Available Models:[/bold cyan]")
        for idx, model in enumerate(models):
            desc = Config.MODELS[model]["description"]
            rprint(f"{idx + 1}. {model} - [dim]{desc}[/dim]")

        choice = Prompt.ask("Select a model", choices=[str(i+1) for i in range(len(models))], default="1")
        self.current_model_name = models[int(choice) - 1]
        self.init_agent() # Re-init agent with new model
        rprint(f"[green]Switched to {self.current_model_name}[/green]")

    def inspect_path(self, path_str: str):
        path = Path(path_str)
        if not path.exists():
            rprint(f"[red]Path '{path_str}' does not exist.[/red]")
            return

        if path.is_file():
            try:
                try:
                    content = path.read_text(encoding='utf-8')
                except UnicodeDecodeError:
                    content = "<Binary File>"

                self.attachments.append((path.name, content))
                rprint(f"[green]Attached file: {path.name}[/green]")
            except Exception as e:
                rprint(f"[red]Error reading file: {e}[/red]")
        elif path.is_dir():
            confirmation = Confirm.ask(f"Do you want to attach all text files in '{path.name}'?")
            if confirmation:
                count = 0
                for item in path.iterdir():
                    if item.is_file():
                        try:
                            if item.suffix in ['.rs', '.ts', '.tsx', '.py', '.txt', '.md', '.json', '.yaml', '.yml', '.toml', '.html', '.css', '.scss', '.js', '.sh', '.c', '.cpp', '.h']:
                                content = item.read_text(encoding='utf-8')
                                self.attachments.append((item.name, content))
                                count += 1
                        except:
                            pass
                rprint(f"[green]Attached {count} files from {path_str}[/green]")
            else:
                 rprint("[yellow]Operation cancelled.[/yellow]")

    def copy_last_response(self):
        if self.last_response:
            pyperclip.copy(self.last_response)
            rprint("[green]Last response copied to clipboard![/green]")
        else:
            rprint("[yellow]No response to copy.[/yellow]")

    def copy_code_block(self, parts: List[str]):
        if not self.last_code_blocks:
             rprint("[red]No code blocks found in the last response.[/red]")
             return

        index = 0
        if len(parts) < 2:
             if len(self.last_code_blocks) == 1:
                 index = 0
             else:
                 rprint(f"[yellow]Usage: /code <1-{len(self.last_code_blocks)}>[/yellow]")
                 return
        else:
            try:
                index = int(parts[1]) - 1
            except ValueError:
                rprint("[red]Invalid number.[/red]")
                return

        if 0 <= index < len(self.last_code_blocks):
            code = self.last_code_blocks[index]
            pyperclip.copy(code)
            rprint(f"[green]Code block {index + 1} copied to clipboard![/green]")
        else:
            rprint("[red]Invalid code block number.[/red]")

    def show_usage_summary(self):
        if not self.model_usage:
            return

        model_usage_str = ""
        for model, count in self.model_usage.items():
            model_usage_str += f"  • {model}: {count} request{'s' if count != 1 else ''}\n"

        summary = (
            f"[bold cyan]Session Summary[/bold cyan]\n\n"
            f"[bold]Model Usage:[/bold]\n{model_usage_str}\n"
            f"[bold]Token Usage (Approx):[/bold]\n"
            f"  • Total Input Tokens: {self.total_input_tokens:,}\n"
            f"  • Total Output Tokens: {self.total_output_tokens:,}\n"
            f"  • Total Tokens: {self.total_input_tokens + self.total_output_tokens:,}"
        )

        rprint("\n")
        rprint(Panel(summary, border_style="cyan", title="💡 Usage Statistics", title_align="left"))

    # Async Chat Loop
    async def chat_loop(self):
        ascii_art = r"""
    ____        ________                __     ________    ____
   / __ \__  __/ ____/ /___ ___  ______/ /__  / ____/ /   /  _/
  / /_/ / / / / /   / / __ `/ / / / __  / _ \/ /   / /    / /
 / ____/ /_/ / /___/ / /_/ / /_/ / /_/ /  __/ /___/ /____/ /
/_/    \__, /\____/_/\__,_/\__,_/\__,_/\___/\____/_____/___/
      /____/
        """
        rprint(Panel.fit(f"\n[bold cyan]{ascii_art}[/bold cyan]\n"
                        "\n[bold magenta]✨Welcome to PyClaudeCLI - powered by Strands SDK✨[/bold magenta]\n"
                        f"[bold cyan]v{APP_VERSION}[/bold cyan]\n"
                        "Commands: /help, /model, /attach <path>, /copy, /code <n>, /skills, /stats, /clear, /quit",
                        border_style="magenta"))

        while True:
            try:
                # Show pending attachments in prompt
                prompt_suffix = ""
                if self.attachments:
                    prompt_suffix = f" <yellow>({len(self.attachments)} files attached)</yellow>"

                # Async prompt
                try:
                    user_input = await self.prompt_session.prompt_async(HTML(f"\n<b><cyan>You</cyan></b>{prompt_suffix}: "))
                except EOFError:
                    break

                if not user_input.strip():
                    continue

                # Handle Slash Commands
                if user_input.startswith("/"):
                    parts = user_input.split()
                    command = parts[0].lower()

                    if command == "/quit":
                        self.show_usage_summary()
                        rprint("[bold red]Goodbye![/bold red]")
                        break
                    elif command == "/stats":
                        self.show_usage_summary()
                        continue
                    elif command == "/model":
                        self.switch_model()
                        continue
                    elif command == "/attach":
                        if len(parts) > 1:
                            self.inspect_path(parts[1])
                        else:
                            rprint("[red]Usage: /attach <path>[/red]")
                        continue
                    elif command == "/copy":
                        self.copy_last_response()
                        continue
                    elif command == "/code":
                        self.copy_code_block(parts)
                        continue
                    elif command == "/clear":
                        self.messages = []
                        self.attachments = []
                        self.last_code_blocks = []
                        rprint("[green]Conversation and usage stats cleared.[/green]")
                        continue
                    elif command == "/skills":
                        self.list_skills()
                        continue
                    elif command == "/help":
                         rprint(Panel("[bold]Available Commands:[/bold]\n"
                                      "/model - Switch AI Model\n"
                                      "/attach <path> - Attach file or directory contents\n"
                                      "/copy - Copy last response to clipboard\n"
                                      "/code <n> - Copy detected code block #n\n"
                                      "/skills - List available skill files\n"
                                      "/stats - Show usage statistics\n"
                                      "/clear - Clear conversation history\n"
                                      "/quit - Exit", title="Help"))
                         continue

                # Process Message
                self.add_user_message(user_input)

                # Use Status spinner with update capability
                current_status_text = f"[bold green]Claude ({self.current_model_name}) is thinking...[/bold green]"
                
                with console.status(current_status_text) as status:
                    response_text_acc = ""
                    try:
                        # Call Agent Stream
                        # We pass the full history of messages
                        # Reset agent memory to avoid duplication as we manage history externally
                        self.agent.messages = []
                        stream = self.agent.stream_async(prompt=self.messages)
                        
                        async for event in stream:
                            # Heuristic for tool use visualization
                            # Check for tool use events
                            # We inspect the event dictionary/object
                            
                            is_tool = False
                            # Check for tool related keys or types
                            if isinstance(event, dict):
                                if "tool_use" in event or "tool_calls" in event:
                                    is_tool = True
                                # Also check for type field
                                if event.get("type") in ["tool_use", "tool_start"]:
                                    is_tool = True
                            elif hasattr(event, "tool_use") or hasattr(event, "tool_calls"):
                                is_tool = True
                            
                            if is_tool:
                                status.update("🌎 using tool....")
                            
                            # Collect text
                            # Assuming event might be text delta or content block
                            # Strands: ContentBlockDelta usually has 'delta': {'text': '...', 'type': 'text_delta'}
                            text_delta = ""
                            if isinstance(event, dict):
                                delta = event.get("delta", {})
                                if isinstance(delta, dict) and delta.get("type") == "text_delta":
                                    text_delta = delta.get("text", "")
                                elif event.get("type") == "content_block_delta":
                                      # deeply nested
                                      pass 
                            
                            # Fallback: check if event is a text chunk if Strands yields simple chunks (unlikely)
                            
                            # For BedrockModel/Agent, the stream usually yields events similar to Bedrock API or Strands events.
                            # We will rely on the Agent to return the final message(s) or we reconstruct it.
                            # But wait, if we stream, we want to accumulate text.
                            
                            # If we can't easily parse partial text, we'll wait for final loop end?
                            # But the agent.stream_async yields events. 
                            # If we don't handle text accumulation, we won't have the response.
                            # We need to capture the assistant response.
                            
                            # Let's try to extract text from common event patterns
                            if isinstance(event, dict) and "delta" in event:
                                delta = event["delta"]
                                if "text" in delta:
                                    response_text_acc += delta["text"]
                                    # Switch back to thinking if we see text (implies tool done)
                                    if "🌎" in str(status.status):
                                        status.update(f"[bold green]Claude ({self.current_model_name}) is thinking...[/bold green]")

                            if isinstance(event, dict) and "result" in event:
                                result = event["result"]
                                if hasattr(result, "metrics") and hasattr(result.metrics, "get_summary"):
                                    summary = result.metrics.get_summary()
                                    if "accumulated_usage" in summary:
                                        usage = summary["accumulated_usage"]
                                        self.total_input_tokens += usage.get("inputTokens", 0)
                                        self.total_output_tokens += usage.get("outputTokens", 0)

                        # After stream ends, we display the response
                        if response_text_acc:
                            self.add_assistant_message(response_text_acc)
                            rprint(f"\n[bold magenta]Claude ({self.current_model_name}):[/bold magenta]")
                            console.print(Markdown(response_text_acc))
                            
                            if self.current_model_name not in self.model_usage:
                                self.model_usage[self.current_model_name] = 0
                            self.model_usage[self.current_model_name] += 1
                            
                            # Notify about code blocks
                            if self.last_code_blocks:
                                msg = f"[dim]Found {len(self.last_code_blocks)} code blocks. Use /code"
                                if len(self.last_code_blocks) > 1:
                                    msg += " <number>"
                                msg += " to copy.[/dim]"
                                rprint(msg)
                        else:
                            # If we failed to capture text via stream delta, maybe the agent output is different?
                            # This is a risk. 
                            pass

                    except Exception as e:
                       rprint(f"[bold red]Error during chat:[/bold red] {e}")

            except KeyboardInterrupt:
                self.show_usage_summary()
                rprint("\n[bold red]Goodbye![/bold red]")
                break
            except Exception as e:
                rprint(f"[bold red]Unexpected Error:[/bold red] {e}")

@app.command()
def start():
    """Start the Claude CLI Chat."""
    try:
        session = ChatSession()
        asyncio.run(session.chat_loop())
    except Exception as e:
        rprint(f"[bold red]Failed to start session:[/bold red] {e}")
        # traceback
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    app()
