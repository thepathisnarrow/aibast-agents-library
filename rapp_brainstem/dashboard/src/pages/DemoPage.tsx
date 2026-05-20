import { useState, useEffect, useCallback } from 'react';
import {
  makeStyles,
  tokens,
  Card,
  Text,
  Badge,
  Spinner,
  Button,
  Subtitle1,
  Dialog,
  DialogSurface,
  DialogTitle,
  DialogBody,
  DialogActions,
  DialogContent,
  Input,
  Textarea,
  Field,
  ProgressBar,
  Dropdown,
  Option,
  Checkbox,
  Tooltip,
  MessageBar,
  MessageBarBody,
  MessageBarTitle,
} from '@fluentui/react-components';
import {
  ArrowClockwise24Regular,
  Add24Regular,
  Open16Regular,
  Save24Regular,
  Delete24Regular,
  Play24Regular,
} from '@fluentui/react-icons';
import type { DashboardData, DemoRequest, DemoRequestDraft } from '../api/types';
import { submitDemoRequest } from '../api/client';

const DRAFT_STORAGE_KEY = 'brainstem_demo_drafts';

const SCENARIO_TEMPLATES = [
  { key: '', label: '(Custom — describe your own)' },
  { key: 'retail_analytics', label: 'Retail Analytics with Real-Time Inventory' },
  { key: 'healthcare_compliance', label: 'Healthcare Data Platform with Governance' },
  { key: 'manufacturing_iot', label: 'Manufacturing IoT with Predictive Alerts' },
  { key: 'financial_services', label: 'Financial Services Reporting with M365 Copilot' },
  { key: 'full_platform', label: 'Complete Data Platform Demo (All Technologies)' },
];

const TECHNOLOGY_OPTIONS = [
  'Fabric Lakehouse',
  'Fabric Mirroring',
  'Real-Time Intelligence',
  'Semantic Model / Power BI',
  'Microsoft Purview',
  'Fabric Data Agent',
  'Copilot Studio',
  'Foundry Agent',
  'M365 Copilot',
  'Event Hubs',
  'Azure SQL',
  'Cosmos DB',
];

const REQUIREMENT_OPTIONS = [
  'Batch ingestion',
  'Streaming / real-time',
  'Data governance',
  'Natural language querying',
  'Teams integration',
  'M365 Copilot integration',
  'Role-based access control',
  'Audit/compliance',
  'Power BI reports',
  'Activator alerts',
];

const useStyles = makeStyles({
  page: {
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  requestList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  requestItem: {
    padding: '16px',
  },
  requestRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  requestDetails: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  agentChips: {
    display: 'flex',
    gap: '4px',
    flexWrap: 'wrap',
    marginTop: '4px',
  },
  wizardStep: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    minWidth: '480px',
  },
  checkboxGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '4px',
  },
  draftBanner: {
    marginBottom: '8px',
  },
  draftList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  draftItem: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 14px',
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground3,
  },
  dropZone: {
    border: `2px dashed ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    padding: '24px',
    textAlign: 'center',
    cursor: 'pointer',
    ':hover': {
      borderTopColor: tokens.colorBrandStroke1,
      borderRightColor: tokens.colorBrandStroke1,
      borderBottomColor: tokens.colorBrandStroke1,
      borderLeftColor: tokens.colorBrandStroke1,
      backgroundColor: tokens.colorNeutralBackground3,
    },
  },
  emptyState: {
    textAlign: 'center',
    padding: '32px',
    color: tokens.colorNeutralForeground3,
  },
});

interface PageProps {
  data: DashboardData | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

// ── Draft Persistence ──────────────────────────────────────────────────────

function loadDrafts(): DemoRequestDraft[] {
  try {
    const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveDrafts(drafts: DemoRequestDraft[]) {
  localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(drafts));
}

function createEmptyDraft(): DemoRequestDraft {
  return {
    id: crypto.randomUUID(),
    step: 0,
    customer_name: '',
    title: '',
    scenario: '',
    template: '',
    requirements: [],
    technologies: [],
    files: [],
    saved_at: new Date().toISOString(),
  };
}

// ── Component ──────────────────────────────────────────────────────────────

export function DemoPage({ data, loading, error: _error, onRefresh }: PageProps) {
  const styles = useStyles();
  const [wizardOpen, setWizardOpen] = useState(false);
  const [drafts, setDrafts] = useState<DemoRequestDraft[]>(loadDrafts);
  const [activeDraft, setActiveDraft] = useState<DemoRequestDraft | null>(null);
  const [wizardStep, setWizardStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [files, setFiles] = useState<File[]>([]);

  // Sync drafts to localStorage whenever they change
  useEffect(() => {
    saveDrafts(drafts);
  }, [drafts]);

  const demos: DemoRequest[] = data?.demos ?? [];

  // ── Wizard Controls ────────────────────────────────────────────────────

  const openNewWizard = useCallback(() => {
    const draft = createEmptyDraft();
    setActiveDraft(draft);
    setWizardStep(0);
    setFiles([]);
    setWizardOpen(true);
  }, []);

  const resumeDraft = useCallback((draft: DemoRequestDraft) => {
    setActiveDraft({ ...draft });
    setWizardStep(draft.step);
    setFiles([]);
    setWizardOpen(true);
  }, []);

  const deleteDraft = useCallback((id: string) => {
    setDrafts(prev => prev.filter(d => d.id !== id));
  }, []);

  const saveCurrentDraft = useCallback(() => {
    if (!activeDraft) return;
    const updated: DemoRequestDraft = {
      ...activeDraft,
      step: wizardStep,
      saved_at: new Date().toISOString(),
    };
    setDrafts(prev => {
      const exists = prev.findIndex(d => d.id === updated.id);
      if (exists >= 0) {
        const copy = [...prev];
        copy[exists] = updated;
        return copy;
      }
      return [...prev, updated];
    });
    setWizardOpen(false);
    setActiveDraft(null);
  }, [activeDraft, wizardStep]);

  const updateDraft = useCallback((patch: Partial<DemoRequestDraft>) => {
    setActiveDraft(prev => prev ? { ...prev, ...patch } : prev);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files);
      setFiles(selected);
      updateDraft({ files: selected.map(f => f.name) });
    }
  };

  const handleSubmit = async () => {
    if (!activeDraft) return;
    setSubmitting(true);
    try {
      await submitDemoRequest({
        title: activeDraft.title,
        customer_name: activeDraft.customer_name,
        scenario: activeDraft.scenario,
        template: activeDraft.template,
        requirements: activeDraft.requirements,
        technologies: activeDraft.technologies,
        files: files.length > 0 ? files : undefined,
      });
      // Remove draft on successful submission
      setDrafts(prev => prev.filter(d => d.id !== activeDraft.id));
      setWizardOpen(false);
      setActiveDraft(null);
      setFiles([]);
      onRefresh();
    } finally {
      setSubmitting(false);
    }
  };

  // ── Status helpers ─────────────────────────────────────────────────────

  const statusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success' as const;
      case 'in-progress': return 'warning' as const;
      case 'queued': return 'informative' as const;
      default: return 'subtle' as const;
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────

  if (loading && !data) {
    return <Spinner label="Loading demo requests..." size="large" />;
  }

  const TOTAL_STEPS = 5;

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <Subtitle1>Demo Requests</Subtitle1>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button appearance="primary" icon={<Add24Regular />} onClick={openNewWizard}>
            New Demo Request
          </Button>
          <Button
            appearance="subtle"
            icon={<ArrowClockwise24Regular />}
            onClick={onRefresh}
            disabled={loading}
          />
        </div>
      </div>

      {/* Drafts section */}
      {drafts.length > 0 && (
        <div className={styles.section}>
          <Text weight="semibold" size={400}>Saved Drafts</Text>
          <div className={styles.draftList}>
            {drafts.map(draft => (
              <div key={draft.id} className={styles.draftItem}>
                <div className={styles.requestDetails}>
                  <Text weight="semibold">
                    {draft.title || draft.customer_name || 'Untitled Draft'}
                  </Text>
                  <Text size={200}>
                    Step {draft.step + 1} of {TOTAL_STEPS} · Saved {new Date(draft.saved_at).toLocaleDateString()}
                  </Text>
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  <Tooltip content="Resume" relationship="label">
                    <Button
                      appearance="subtle"
                      icon={<Play24Regular />}
                      onClick={() => resumeDraft(draft)}
                    />
                  </Tooltip>
                  <Tooltip content="Delete draft" relationship="label">
                    <Button
                      appearance="subtle"
                      icon={<Delete24Regular />}
                      onClick={() => deleteDraft(draft.id!)}
                    />
                  </Tooltip>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Active Requests */}
      <div className={styles.section}>
        <Text weight="semibold" size={400}>Submitted Requests</Text>
        <div className={styles.requestList}>
          {demos.length === 0 && (
            <div className={styles.emptyState}>
              <Text italic size={200}>No demo requests yet. Create one above!</Text>
            </div>
          )}
          {demos.map(demo => (
            <Card key={demo.id} className={styles.requestItem}>
              <div className={styles.requestRow}>
                <div className={styles.requestDetails}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Text weight="semibold">{demo.title}</Text>
                    <Badge appearance="filled" color={statusColor(demo.status)} size="small">
                      {demo.status}
                    </Badge>
                  </div>
                  <Text size={200}>
                    {demo.customer_name}{demo.template ? ` · ${demo.template}` : ''}
                  </Text>
                  {demo.assigned_agents.length > 0 && (
                    <div className={styles.agentChips}>
                      {demo.assigned_agents.map(agent => (
                        <Badge key={agent} appearance="outline" size="small">{agent}</Badge>
                      ))}
                    </div>
                  )}
                  <Text size={100} style={{ color: tokens.colorNeutralForeground3 }}>
                    Created {new Date(demo.created_at).toLocaleDateString()}
                    {demo.updated_at !== demo.created_at && ` · Updated ${new Date(demo.updated_at).toLocaleDateString()}`}
                  </Text>
                </div>
                {demo.url && (
                  <Tooltip content="Open in GitHub" relationship="label">
                    <Button
                      appearance="subtle"
                      icon={<Open16Regular />}
                      as="a"
                      href={demo.url}
                      target="_blank"
                    />
                  </Tooltip>
                )}
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* ── Wizard Dialog ─────────────────────────────────────────────────── */}
      <Dialog open={wizardOpen} onOpenChange={(_, d) => {
        if (!d.open) {
          // Auto-save draft when closing without submitting
          if (activeDraft && (activeDraft.title || activeDraft.customer_name || activeDraft.scenario)) {
            saveCurrentDraft();
          } else {
            setWizardOpen(false);
            setActiveDraft(null);
          }
        }
      }}>
        <DialogSurface>
          <DialogBody>
            <DialogTitle>
              New Demo Request — Step {wizardStep + 1} of {TOTAL_STEPS}
            </DialogTitle>
            <DialogContent>
              <ProgressBar value={(wizardStep + 1) / TOTAL_STEPS} />
              <div className={styles.wizardStep} style={{ marginTop: 16 }}>
                {/* Step 1: Customer Info */}
                {wizardStep === 0 && (
                  <>
                    <Field label="Customer Name" required>
                      <Input
                        value={activeDraft?.customer_name ?? ''}
                        onChange={(_, d) => updateDraft({ customer_name: d.value })}
                        placeholder="e.g. Contoso Ltd"
                      />
                    </Field>
                    <Field label="Demo Title" required>
                      <Input
                        value={activeDraft?.title ?? ''}
                        onChange={(_, d) => updateDraft({ title: d.value })}
                        placeholder="e.g. Real-Time Inventory Analytics"
                      />
                    </Field>
                  </>
                )}

                {/* Step 2: Scenario */}
                {wizardStep === 1 && (
                  <>
                    <Field label="Start from a template (optional)">
                      <Dropdown
                        value={SCENARIO_TEMPLATES.find(t => t.key === activeDraft?.template)?.label ?? SCENARIO_TEMPLATES[0].label}
                        selectedOptions={[activeDraft?.template ?? '']}
                        onOptionSelect={(_, d) => updateDraft({ template: d.optionValue ?? '' })}
                      >
                        {SCENARIO_TEMPLATES.map(t => (
                          <Option key={t.key} value={t.key}>{t.label}</Option>
                        ))}
                      </Dropdown>
                    </Field>
                    <Field label="Scenario Description" required>
                      <Textarea
                        value={activeDraft?.scenario ?? ''}
                        onChange={(_, d) => updateDraft({ scenario: d.value })}
                        placeholder="Describe what the customer wants to see..."
                        rows={5}
                      />
                    </Field>
                  </>
                )}

                {/* Step 3: Requirements & Technologies */}
                {wizardStep === 2 && (
                  <>
                    <Field label="Requirements">
                      <div className={styles.checkboxGrid}>
                        {REQUIREMENT_OPTIONS.map(req => (
                          <Checkbox
                            key={req}
                            label={req}
                            checked={activeDraft?.requirements.includes(req)}
                            onChange={(_, d) => {
                              const reqs = activeDraft?.requirements ?? [];
                              updateDraft({
                                requirements: d.checked
                                  ? [...reqs, req]
                                  : reqs.filter(r => r !== req),
                              });
                            }}
                          />
                        ))}
                      </div>
                    </Field>
                    <Field label="Technologies">
                      <div className={styles.checkboxGrid}>
                        {TECHNOLOGY_OPTIONS.map(tech => (
                          <Checkbox
                            key={tech}
                            label={tech}
                            checked={activeDraft?.technologies.includes(tech)}
                            onChange={(_, d) => {
                              const techs = activeDraft?.technologies ?? [];
                              updateDraft({
                                technologies: d.checked
                                  ? [...techs, tech]
                                  : techs.filter(t => t !== tech),
                              });
                            }}
                          />
                        ))}
                      </div>
                    </Field>
                  </>
                )}

                {/* Step 4: File Attachments */}
                {wizardStep === 3 && (
                  <>
                    <Text>
                      Attach supporting files: transcripts, screenshots, reference materials, or data samples.
                    </Text>
                    <div className={styles.dropZone}>
                      <input
                        type="file"
                        multiple
                        accept=".vtt,.docx,.png,.jpg,.jpeg,.pdf,.xlsx,.csv"
                        onChange={handleFileChange}
                        style={{ display: 'none' }}
                        id="demo-file-upload"
                      />
                      <label htmlFor="demo-file-upload" style={{ cursor: 'pointer' }}>
                        <Text size={300}>
                          {files.length > 0
                            ? `${files.length} file(s) selected: ${files.map(f => f.name).join(', ')}`
                            : activeDraft?.files && activeDraft.files.length > 0
                            ? `Previously attached: ${activeDraft.files.join(', ')} (re-select to keep)`
                            : 'Click to select files (.vtt, .docx, .pdf, .xlsx, images)'}
                        </Text>
                      </label>
                    </div>
                  </>
                )}

                {/* Step 5: Review */}
                {wizardStep === 4 && (
                  <>
                    <MessageBar intent="info" className={styles.draftBanner}>
                      <MessageBarBody>
                        <MessageBarTitle>Review & Submit</MessageBarTitle>
                        Confirm the details below, then submit to queue the demo for orchestration.
                      </MessageBarBody>
                    </MessageBar>
                    <Field label="Customer">
                      <Text>{activeDraft?.customer_name}</Text>
                    </Field>
                    <Field label="Title">
                      <Text>{activeDraft?.title}</Text>
                    </Field>
                    <Field label="Template">
                      <Text>
                        {activeDraft?.template
                          ? SCENARIO_TEMPLATES.find(t => t.key === activeDraft.template)?.label
                          : 'Custom'}
                      </Text>
                    </Field>
                    <Field label="Scenario">
                      <Text>{activeDraft?.scenario || '(none)'}</Text>
                    </Field>
                    <Field label="Requirements">
                      <Text>
                        {activeDraft?.requirements.length
                          ? activeDraft.requirements.join(', ')
                          : '(none selected)'}
                      </Text>
                    </Field>
                    <Field label="Technologies">
                      <Text>
                        {activeDraft?.technologies.length
                          ? activeDraft.technologies.join(', ')
                          : '(none selected)'}
                      </Text>
                    </Field>
                    <Field label="Files">
                      <Text>
                        {files.length > 0
                          ? files.map(f => f.name).join(', ')
                          : activeDraft?.files?.length
                          ? activeDraft.files.join(', ')
                          : 'None attached'}
                      </Text>
                    </Field>
                  </>
                )}
              </div>
            </DialogContent>
            <DialogActions>
              <Button
                appearance="secondary"
                icon={<Save24Regular />}
                onClick={saveCurrentDraft}
              >
                Save Draft
              </Button>
              <div style={{ flex: 1 }} />
              {wizardStep > 0 && (
                <Button appearance="secondary" onClick={() => setWizardStep(s => s - 1)}>
                  Back
                </Button>
              )}
              {wizardStep < TOTAL_STEPS - 1 ? (
                <Button
                  appearance="primary"
                  onClick={() => setWizardStep(s => s + 1)}
                  disabled={wizardStep === 0 && (!activeDraft?.customer_name || !activeDraft?.title)}
                >
                  Next
                </Button>
              ) : (
                <Button
                  appearance="primary"
                  onClick={handleSubmit}
                  disabled={submitting || !activeDraft?.title || !activeDraft?.customer_name}
                >
                  {submitting ? 'Submitting...' : 'Submit Request'}
                </Button>
              )}
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
}
