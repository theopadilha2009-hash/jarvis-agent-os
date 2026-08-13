#!/usr/bin/env python3
"""Shared action and run contracts for the JARVIS web and local runtimes.

This module is intentionally stdlib-only. It centralizes capability metadata,
risk policy and the durable local run envelope without providing arbitrary
shell execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
import json
import os
import re
import tempfile
import uuid


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_VERSION = "jarvis-actions/1"
RUN_PROTOCOL = "jarvis-run/1"
TERMINAL_STATES = {"completed", "failed", "canceled"}
VALID_STATES = {
    "planned",
    "waiting_confirmation",
    "running",
    *TERMINAL_STATES,
}
RISK_LEVELS = {"read_only", "runtime_write", "local_write", "external_write", "code_write"}
CONFIRMATION_MODES = {"none", "explicit_request", "interactive"}
RUN_ID_PATTERN = re.compile(r"^jr-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$")


@dataclass(frozen=True)
class ActionSpec:
    name: str
    label: str
    description: str
    executor: str
    risk: str = "read_only"
    confirmation: str = "none"
    private: bool = False
    scopes: tuple[str, ...] = ("web", "cli")
    intents: tuple[str, ...] = ()
    parameters: dict[str, Any] | None = None

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["scopes"] = list(self.scopes)
        value["intents"] = list(self.intents)
        value["parameters"] = dict(self.parameters or {})
        value["requires_confirmation"] = self.confirmation == "interactive"
        return value


def _object_schema(**properties: Any) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "additionalProperties": False}


ACTION_SPECS = (
    ActionSpec("assistant_chat", "Conversar", "Responder usando contexto e o provedor disponível.", "brain", intents=("assistant",)),
    ActionSpec("web_research", "Pesquisar com fontes", "Pesquisar fontes públicas e devolver evidências verificáveis.", "web", intents=("research", "research_plan")),
    ActionSpec("personal_overview", "Central pessoal", "Cruzar agenda, memória, worker e atividade recente.", "control_plane", private=True, intents=("personal_overview", "daily_brief")),
    ActionSpec("memory_view", "Ler memória", "Consultar memórias privadas confirmadas.", "memory", private=True, intents=("memory_view",)),
    ActionSpec("memory_search", "Buscar na memória", "Pesquisar memória confirmada por conteúdo, origem e projeto.", "memory", private=True, intents=("memory_search",)),
    ActionSpec("memory_save", "Guardar memória", "Persistir aprendizado, preferência ou decisão explícita.", "memory", "local_write", "explicit_request", True, intents=("memory_save",)),
    ActionSpec("contact_view", "Ler contatos", "Consultar contatos privados ativos.", "contacts", private=True, intents=("contact_view",)),
    ActionSpec("contact_save", "Guardar contato", "Persistir um contato fornecido explicitamente.", "contacts", "local_write", "explicit_request", True, intents=("contact_save",)),
    ActionSpec("contact_archive", "Arquivar contato", "Arquivar um contato privado sem apagar histórico.", "contacts", "local_write", "interactive", True, intents=("contact_archive",)),
    ActionSpec("agenda_view", "Ver agenda", "Consultar itens privados pendentes.", "agenda", private=True, intents=("agenda_view",)),
    ActionSpec("agenda_note", "Adicionar à agenda", "Criar tarefa ou lembrete privado.", "agenda", "local_write", "explicit_request", True, intents=("agenda_note", "task_add")),
    ActionSpec("agenda_complete", "Concluir agenda", "Marcar um item privado como concluído.", "agenda", "local_write", "explicit_request", True, intents=("agenda_complete",)),
    ActionSpec("open_application", "Abrir aplicativo", "Abrir um aplicativo allowlisted no Mac pareado.", "mac", "runtime_write", "explicit_request", True, intents=("open_application",)),
    ActionSpec("close_application", "Fechar aplicativo", "Fechar um aplicativo allowlisted no Mac pareado.", "mac", "runtime_write", "explicit_request", True, intents=("close_application",)),
    ActionSpec("screen_capture", "Capturar tela", "Capturar a tela do Mac e devolver evidência.", "mac", "runtime_write", "explicit_request", True, intents=("screen_capture",)),
    ActionSpec("screen_record", "Gravar tela", "Abrir o gravador nativo para confirmação visível.", "mac", "runtime_write", "explicit_request", True, intents=("screen_record",)),
    ActionSpec("github_overview", "Inspecionar GitHub", "Ler conta e repositórios sem alterá-los.", "github", private=True, intents=("github_overview",)),
    ActionSpec("storage_scan", "Analisar armazenamento", "Ler metadados e localizar arquivos grandes.", "mac", private=True, intents=("storage_scan",)),
    ActionSpec("system_memory", "Diagnosticar computador", "Inspecionar memória e processos temporários do JARVIS.", "mac", "runtime_write", "explicit_request", True, intents=("system_memory",)),
    ActionSpec("device_run", "Executar sequência", "Executar de duas a seis ações allowlisted em ordem, interrompendo na primeira falha.", "mac", "runtime_write", "explicit_request", True, intents=("device_run",)),
    ActionSpec("local_utility", "Utilitário local", "Executar uma utilidade pessoal estreitamente allowlisted.", "local_worker", "runtime_write", "explicit_request", True, intents=("speak", "image_convert", "image_to_pdf", "message_draft", "files_triage", "capture_note")),
    ActionSpec("voice_design", "Criar voz", "Gerar e salvar uma nova voz do JARVIS no provedor configurado.", "voice", "external_write", "interactive", True, intents=("voice_design",)),
    ActionSpec(
        "message_send",
        "Enviar mensagem",
        "Enviar texto exato para destinatário explícito pelo Mac pareado.",
        "messages",
        "external_write",
        "interactive",
        True,
        intents=("message_send",),
        parameters=_object_schema(recipient={"type": "string"}, message={"type": "string"}),
    ),
    ActionSpec("self_edit", "Autoeditar JARVIS", "Editar, testar e commitar o próprio JARVIS em ambiente isolado.", "local_worker", "code_write", "interactive", True, intents=("self_edit", "self_evolve")),
    ActionSpec("planning", "Planejar", "Gerar plano, brief ou checklist sem executar produção.", "planner", "runtime_write", "explicit_request", intents=("planning", "blueprint", "n8n_blueprint", "app_blueprint", "automation_blueprint", "no_claude", "unclear")),
    ActionSpec("project_inspect", "Inspecionar projeto", "Ler arquivos, Git e testes de projeto registrado.", "local_worker", private=True, intents=("project_inspect", "project_fix_or_inspect", "project_fix", "project_qa", "browser_qa", "final_gate", "open_project")),
)

ACTION_REGISTRY = {item.name: item for item in ACTION_SPECS}
INTENT_INDEX = {
    intent: item
    for item in ACTION_SPECS
    for intent in item.intents
}


def validate_registry() -> list[str]:
    errors: list[str] = []
    for name, spec in ACTION_REGISTRY.items():
        if name != spec.name:
            errors.append(f"registry key mismatch: {name}")
        if spec.risk not in RISK_LEVELS:
            errors.append(f"{name}: invalid risk {spec.risk}")
        if spec.confirmation not in CONFIRMATION_MODES:
            errors.append(f"{name}: invalid confirmation {spec.confirmation}")
    return errors


def action_for_intent(intent: str | None) -> ActionSpec | None:
    return INTENT_INDEX.get(str(intent or "").strip())


def action_payloads(scope: str | None = None) -> list[dict[str, Any]]:
    rows = ACTION_SPECS
    if scope:
        rows = tuple(item for item in rows if scope in item.scopes)
    return [item.public_dict() for item in rows]


def needs_interactive_confirmation(intent: str | None) -> bool:
    action = action_for_intent(intent)
    return bool(action and action.confirmation == "interactive")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_run_dir() -> Path:
    configured = os.environ.get("JARVIS_AGENT_RUN_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if os.environ.get("VERCEL"):
        return Path("/tmp/jarvis-agent-runs")
    return ROOT / "05_EXECUCAO" / "65_AGENT_RUNS"


class RunStore:
    """Small append-in-record store for resumable, auditable agent runs."""

    def __init__(self, directory: Path | None = None):
        self.directory = Path(directory or default_run_dir())
        self._lock = RLock()

    def _path(self, run_id: str) -> Path:
        if not RUN_ID_PATTERN.fullmatch(str(run_id or "")):
            raise ValueError("invalid run id")
        return self.directory / f"{run_id}.json"

    def _write(self, record: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self._path(record["id"])
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.directory,
            prefix=f".{record['id']}.",
            suffix=".tmp",
            delete=False,
        )
        temporary = Path(handle.name)
        try:
            with handle:
                json.dump(record, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()

    def create(
        self,
        command: str,
        *,
        action: str = "assistant_chat",
        source: str = "web",
        state: str = "planned",
        plan: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if state not in VALID_STATES:
            raise ValueError("invalid run state")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_id = f"jr-{stamp}-{uuid.uuid4().hex[:8]}"
        created_at = utc_now()
        record = {
            "protocol": RUN_PROTOCOL,
            "id": run_id,
            "state": state,
            "action": action if action in ACTION_REGISTRY else "assistant_chat",
            "source": str(source or "web")[:40],
            "command": str(command or "")[:8_000],
            "plan": list(plan or []),
            "events": [{
                "type": "RUN_CREATED",
                "state": state,
                "timestamp": created_at,
            }],
            "result": None,
            "evidence": [],
            "error": "",
            "created_at": created_at,
            "updated_at": created_at,
            "metadata": dict(metadata or {}),
        }
        with self._lock:
            self._write(record)
        return record

    def get(self, run_id: str) -> dict[str, Any] | None:
        try:
            path = self._path(run_id)
        except ValueError:
            return None
        with self._lock:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        return value if isinstance(value, dict) else None

    def list(self, *, limit: int = 30, states: set[str] | None = None) -> list[dict[str, Any]]:
        """Return newest valid records without trusting filenames or malformed JSON."""
        selected_states = {state for state in (states or set()) if state in VALID_STATES}
        safe_limit = max(1, min(int(limit or 30), 100))
        records = []
        with self._lock:
            try:
                paths = list(self.directory.glob("jr-*.json"))
            except OSError:
                paths = []
            for path in paths:
                run_id = path.stem
                if not RUN_ID_PATTERN.fullmatch(run_id):
                    continue
                record = self.get(run_id)
                if not record or selected_states and record.get("state") not in selected_states:
                    continue
                records.append(record)
        records.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
        return records[:safe_limit]

    def update(
        self,
        run_id: str,
        *,
        state: str | None = None,
        result: Any = None,
        evidence: list[Any] | None = None,
        error: str | None = None,
        event_type: str = "RUN_UPDATED",
        event_detail: str = "",
    ) -> dict[str, Any] | None:
        if state is not None and state not in VALID_STATES:
            raise ValueError("invalid run state")
        with self._lock:
            record = self.get(run_id)
            if not record:
                return None
            if record.get("state") in TERMINAL_STATES and state not in {None, record.get("state")}:
                raise ValueError("terminal run cannot change state")
            if state is not None:
                record["state"] = state
            if result is not None:
                record["result"] = result
            if evidence is not None:
                record["evidence"] = list(evidence)
            if error is not None:
                record["error"] = str(error)[:4_000]
            timestamp = utc_now()
            record["updated_at"] = timestamp
            record.setdefault("events", []).append({
                "type": str(event_type or "RUN_UPDATED")[:80],
                "state": record["state"],
                "detail": str(event_detail or "")[:1_000],
                "timestamp": timestamp,
            })
            self._write(record)
            return record

    def cancel(self, run_id: str) -> dict[str, Any] | None:
        record = self.get(run_id)
        if not record:
            return None
        if record.get("state") in TERMINAL_STATES:
            return record
        return self.update(run_id, state="canceled", event_type="RUN_CANCELED")


def run_public_payload(record: dict[str, Any] | None) -> dict[str, Any]:
    if not record:
        return {}
    action = ACTION_REGISTRY.get(record.get("action"))
    return {
        "run_id": record.get("id"),
        "state": record.get("state"),
        "command": record.get("command") or "",
        "source": record.get("source") or "",
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "plan": record.get("plan") or [],
        "events": record.get("events") or [],
        "result": record.get("result"),
        "evidence": record.get("evidence") or [],
        "error": record.get("error") or "",
        "needs_confirmation": record.get("state") == "waiting_confirmation",
        "action": action.public_dict() if action else None,
    }


def run_summary_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Compact history row; detailed events stay available at GET /runs/<id>."""
    action = ACTION_REGISTRY.get(record.get("action"))
    return {
        "run_id": record.get("id"),
        "state": record.get("state"),
        "command": str(record.get("command") or "")[:500],
        "action": action.public_dict() if action else None,
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "evidence": list(record.get("evidence") or [])[:12],
        "error": str(record.get("error") or "")[:500],
        "event_count": len(record.get("events") or []),
        "retryable": record.get("state") in {"failed", "canceled"},
    }


REGISTRY_ERRORS = validate_registry()
if REGISTRY_ERRORS:
    raise RuntimeError("invalid JARVIS action registry: " + "; ".join(REGISTRY_ERRORS))
