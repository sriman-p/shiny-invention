/**
 * agent-model-picker.tsx — Agent + Model selector with the agent's full
 * model catalog grouped (e.g. GPT-5.5 ▸ low|medium|high|xhigh for Codex).
 *
 * Two components:
 *   - <AgentSelect>: just the agent dropdown
 *   - <ModelSelect>: just the model dropdown (with grouped options +
 *     "Custom model id…" escape hatch + free-text input)
 *   - <AgentModelPicker>: composed agent + model selector for use in tables
 *
 * Choosing an agent surfaces every model that agent supports, not a curated
 * subset. The custom model id field is always available so users can
 * experiment with brand-new model ids the registry hasn't been updated for.
 */
'use client';

import { useId, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import type { AgentSpec } from '@/lib/types';

export const DEFAULT_MODEL_VALUE = '__agent_default__';
export const CUSTOM_MODEL_VALUE = '__custom_model__';

export function getAgent(agents: AgentSpec[], agentId: string): AgentSpec | undefined {
  return agents.find((agent) => agent.id === agentId);
}

export function getFlatModelOptions(agent: AgentSpec | undefined): string[] {
  if (!agent) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  if (agent.model) {
    seen.add(agent.model);
    out.push(agent.model);
  }
  for (const id of agent.model_options || []) {
    if (id && !seen.has(id)) {
      seen.add(id);
      out.push(id);
    }
  }
  return out;
}

export function AgentSelect({
  agents,
  value,
  onChange,
  className,
  triggerClassName,
}: {
  agents: AgentSpec[];
  value: string;
  onChange: (agentId: string) => void;
  className?: string;
  triggerClassName?: string;
}) {
  return (
    <Select value={value} onValueChange={(next) => onChange(next ?? value)}>
      <SelectTrigger className={cn('h-8 text-xs', triggerClassName)}>
        <SelectValue placeholder="Provider" />
      </SelectTrigger>
      <SelectContent className={className}>
        <SelectGroup>
          <SelectLabel className="text-[10px] uppercase tracking-wider text-muted-foreground/60">
            Available providers
          </SelectLabel>
          {agents.map((agent) => (
            <SelectItem key={agent.id} value={agent.id}>
              {agent.display_name}
              {!agent.available && (
                <span className="ml-1 text-[10px] text-muted-foreground/60">(not configured)</span>
              )}
            </SelectItem>
          ))}
          {agents.length === 0 && <SelectItem value="codex">OpenAI Codex CLI</SelectItem>}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

interface ModelSelectProps {
  agent: AgentSpec | undefined;
  modelId: string;
  /** True when the model_id is a free-text custom id (controlled by the parent). */
  isCustom: boolean;
  onChange: (next: { modelId: string; isCustom: boolean }) => void;
  className?: string;
  triggerClassName?: string;
  customPlaceholder?: string;
}

export function ModelSelect({
  agent,
  modelId,
  isCustom,
  onChange,
  className,
  triggerClassName,
  customPlaceholder = 'custom model id',
}: ModelSelectProps) {
  // Live discovery: ask the backend which models the agent's ACP adapter
  // actually advertises and prefer that list over the static catalog so the
  // user can never pick a model the adapter would reject.
  const { data: discovery } = useQuery({
    queryKey: ['agent-models', agent?.id],
    queryFn: () => api.getAgentModels(agent!.id),
    enabled: Boolean(agent?.id),
    staleTime: 5 * 60_000,
  });

  const liveModels = discovery?.discovered ? discovery.models : null;

  const flatOptions = useMemo(() => {
    if (liveModels && liveModels.length > 0) return liveModels;
    return getFlatModelOptions(agent);
  }, [liveModels, agent]);

  // When live models are available, present them as one flat group so the
  // grouped (static) labels never show ids the adapter wouldn't accept.
  const groups = liveModels && liveModels.length > 0
    ? []
    : (agent?.model_groups ?? []);
  const knownIds = new Set(flatOptions);
  const fallbackToCustom = isCustom || (modelId !== '' && !knownIds.has(modelId));

  const selectValue = fallbackToCustom
    ? CUSTOM_MODEL_VALUE
    : modelId === ''
      ? DEFAULT_MODEL_VALUE
      : modelId;

  const inputId = useId();

  const handleSelect = (value: string) => {
    if (value === DEFAULT_MODEL_VALUE) {
      onChange({ modelId: '', isCustom: false });
      return;
    }
    if (value === CUSTOM_MODEL_VALUE) {
      onChange({ modelId, isCustom: true });
      return;
    }
    onChange({ modelId: value, isCustom: false });
  };

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <Select value={selectValue} onValueChange={(next) => handleSelect(next ?? selectValue)}>
        <SelectTrigger className={cn('h-8 text-xs', triggerClassName)}>
          <SelectValue placeholder="Model" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value={DEFAULT_MODEL_VALUE}>
              {agent?.model ? `Default (${agent.model})` : 'Agent default'}
            </SelectItem>
          </SelectGroup>
          {groups.length > 0 ? (
            groups.map((group) => (
              <SelectGroup key={group.label}>
                <SelectLabel className="text-[10px] uppercase tracking-wider text-muted-foreground/60">
                  {group.label}
                </SelectLabel>
                {group.model_ids.map((modelOption) => (
                  <SelectItem key={modelOption} value={modelOption}>
                    {modelOption}
                  </SelectItem>
                ))}
              </SelectGroup>
            ))
          ) : (
            <SelectGroup>
              <SelectLabel className="text-[10px] uppercase tracking-wider text-muted-foreground/60">
                Models
              </SelectLabel>
              {flatOptions.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectGroup>
          )}
          <SelectSeparator />
          <SelectGroup>
            <SelectItem value={CUSTOM_MODEL_VALUE}>Custom model id…</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>
      {fallbackToCustom && (
        <Input
          id={inputId}
          value={modelId}
          placeholder={customPlaceholder}
          onChange={(event) => onChange({ modelId: event.target.value, isCustom: true })}
          className="h-8 text-xs font-mono"
        />
      )}
    </div>
  );
}

export function AgentModelPicker({
  agents,
  agentId,
  modelId,
  isCustom,
  onAgentChange,
  onModelChange,
  className,
}: {
  agents: AgentSpec[];
  agentId: string;
  modelId: string;
  isCustom: boolean;
  onAgentChange: (agentId: string) => void;
  onModelChange: (next: { modelId: string; isCustom: boolean }) => void;
  className?: string;
}) {
  const agent = getAgent(agents, agentId);
  return (
    <div className={cn('flex flex-col gap-2 sm:flex-row sm:items-start', className)}>
      <AgentSelect
        agents={agents}
        value={agentId}
        onChange={onAgentChange}
        triggerClassName="w-full sm:w-[180px]"
      />
      <ModelSelect
        agent={agent}
        modelId={modelId}
        isCustom={isCustom}
        onChange={onModelChange}
        className="flex-1 min-w-0"
        triggerClassName="w-full sm:w-[220px]"
      />
    </div>
  );
}
