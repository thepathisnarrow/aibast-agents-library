import { useState } from 'react';
import {
  makeStyles,
  tokens,
  Card,
  CardHeader,
  Text,
  Badge,
  Spinner,
  Button,
  Subtitle1,
  Dialog,
  DialogTrigger,
  DialogSurface,
  DialogTitle,
  DialogBody,
  DialogActions,
  DialogContent,
  Input,
  Textarea,
  Field,
  ProgressBar,
} from '@fluentui/react-components';
import {
  ArrowClockwise24Regular,
  Add24Regular,
  ChevronRight24Regular,
  ChevronDown24Regular,
  Bot24Regular,
} from '@fluentui/react-icons';
import { useNavigate } from 'react-router-dom';
import type { DashboardData } from '../api/types';
import { submitDemoRequest } from '../api/client';

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
  agentGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
    gap: '12px',
  },
  agentCard: {
    padding: '16px',
  },
  agentIcon: {
    color: tokens.colorBrandForeground1,
    marginBottom: '8px',
  },

  wizardStep: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    minWidth: '400px',
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
});

interface PageProps {
  data: DashboardData | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

const SYSTEM_AGENT_NAMES = ['Basic', 'Context Memory', 'Hacker News', 'Manage Memory'];

export function AgentsPage({ data, loading, error: _error, onRefresh }: PageProps) {
  const styles = useStyles();
  const navigate = useNavigate();
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState(0);
  const [projectTitle, setProjectTitle] = useState('');
  const [projectDesc, setProjectDesc] = useState('');
  const [projectFiles, setProjectFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [systemExpanded, setSystemExpanded] = useState(false);

  if (loading && !data) {
    return <Spinner label="Loading agents..." size="large" />;
  }

  if (!data) return null;

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await submitDemoRequest({
        title: projectTitle,
        customer_name: '',
        scenario: projectDesc,
        template: '',
        requirements: [],
        technologies: [],
        files: projectFiles.length > 0 ? projectFiles : undefined,
      });
      setWizardOpen(false);
      setWizardStep(0);
      setProjectTitle('');
      setProjectDesc('');
      setProjectFiles([]);
      onRefresh();
      navigate('/demos');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setProjectFiles(Array.from(e.target.files));
    }
  };

  const statusColor = (status: string) => {
    switch (status) {
      case 'ready': return 'success' as const;
      case 'busy': return 'warning' as const;
      default: return 'danger' as const;
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <Subtitle1>Agents</Subtitle1>
        <div style={{ display: 'flex', gap: 8 }}>
          <Dialog open={wizardOpen} onOpenChange={(_, d) => setWizardOpen(d.open)}>
            <DialogTrigger disableButtonEnhancement>
              <Button appearance="primary" icon={<Add24Regular />}>
                Submit Demo
              </Button>
            </DialogTrigger>
            <DialogSurface>
              <DialogBody>
                <DialogTitle>
                  Submit a Project — Step {wizardStep + 1} of 3
                </DialogTitle>
                <DialogContent>
                  <ProgressBar value={(wizardStep + 1) / 3} />
                  <div className={styles.wizardStep} style={{ marginTop: 16 }}>
                    {wizardStep === 0 && (
                      <>
                        <Field label="Project Name" required>
                          <Input
                            value={projectTitle}
                            onChange={(_, d) => setProjectTitle(d.value)}
                            placeholder="e.g. Contoso Analytics Demo"
                          />
                        </Field>
                        <Field label="Description" required>
                          <Textarea
                            value={projectDesc}
                            onChange={(_, d) => setProjectDesc(d.value)}
                            placeholder="High-level description of the demo you need built..."
                            rows={4}
                          />
                        </Field>
                      </>
                    )}
                    {wizardStep === 1 && (
                      <>
                        <Text>
                          Attach any supporting files: transcripts (.vtt, .docx),
                          screenshots, or reference materials.
                        </Text>
                        <div className={styles.dropZone}>
                          <input
                            type="file"
                            multiple
                            accept=".vtt,.docx,.png,.jpg,.jpeg,.pdf"
                            onChange={handleFileChange}
                            style={{ display: 'none' }}
                            id="file-upload"
                          />
                          <label htmlFor="file-upload" style={{ cursor: 'pointer' }}>
                            <Text size={300}>
                              {projectFiles.length > 0
                                ? `${projectFiles.length} file(s) selected`
                                : 'Click to select files (.vtt, .docx, images, .pdf)'}
                            </Text>
                          </label>
                        </div>
                      </>
                    )}
                    {wizardStep === 2 && (
                      <>
                        <Text weight="semibold">Review your submission:</Text>
                        <Field label="Name">
                          <Text>{projectTitle}</Text>
                        </Field>
                        <Field label="Description">
                          <Text>{projectDesc}</Text>
                        </Field>
                        <Field label="Files">
                          <Text>
                            {projectFiles.length > 0
                              ? projectFiles.map(f => f.name).join(', ')
                              : 'None attached'}
                          </Text>
                        </Field>
                      </>
                    )}
                  </div>
                </DialogContent>
                <DialogActions>
                  {wizardStep > 0 && (
                    <Button appearance="secondary" onClick={() => setWizardStep(s => s - 1)}>
                      Back
                    </Button>
                  )}
                  {wizardStep < 2 ? (
                    <Button
                      appearance="primary"
                      onClick={() => setWizardStep(s => s + 1)}
                      disabled={wizardStep === 0 && (!projectTitle || !projectDesc)}
                    >
                      Next
                    </Button>
                  ) : (
                    <Button
                      appearance="primary"
                      onClick={handleSubmit}
                      disabled={submitting}
                    >
                      {submitting ? 'Submitting...' : 'Submit'}
                    </Button>
                  )}
                  <DialogTrigger disableButtonEnhancement>
                    <Button appearance="secondary">Cancel</Button>
                  </DialogTrigger>
                </DialogActions>
              </DialogBody>
            </DialogSurface>
          </Dialog>

          <Button
            appearance="subtle"
            icon={<ArrowClockwise24Regular />}
            onClick={onRefresh}
            disabled={loading}
          />
        </div>
      </div>

      {/* Loaded Agents */}
      <div className={styles.section}>
        <Text weight="semibold" size={400}>Brainstem Agents Loaded</Text>
        <div className={styles.agentGrid}>
          {data.agents.loaded
            .filter(agent => !SYSTEM_AGENT_NAMES.includes(agent.name))
            .map(agent => (
              <Card key={agent.name} className={styles.agentCard}>
                <CardHeader
                  image={<Bot24Regular className={styles.agentIcon} />}
                  header={<Text weight="semibold">{agent.name}</Text>}
                  action={
                    <Badge appearance="filled" color={statusColor(agent.status)} size="small">
                      {agent.status}
                    </Badge>
                  }
                />
                <Text size={200}>{agent.description}</Text>
              </Card>
            ))}
        </div>
      </div>

      {/* Brainstem System Agents (collapsible) */}
      <div className={styles.section}>
        <Button
          appearance="subtle"
          icon={systemExpanded ? <ChevronDown24Regular /> : <ChevronRight24Regular />}
          onClick={() => setSystemExpanded(!systemExpanded)}
        >
          <Text weight="semibold" size={400}>Brainstem System ({data.agents.loaded.filter(a => SYSTEM_AGENT_NAMES.includes(a.name)).length})</Text>
        </Button>
        {systemExpanded && (
          <div className={styles.agentGrid}>
            {data.agents.loaded
              .filter(agent => SYSTEM_AGENT_NAMES.includes(agent.name))
              .map(agent => (
                <Card key={agent.name} className={styles.agentCard}>
                  <CardHeader
                    image={<Bot24Regular className={styles.agentIcon} />}
                    header={<Text weight="semibold">{agent.name}</Text>}
                    action={
                      <Badge appearance="filled" color={statusColor(agent.status)} size="small">
                        {agent.status}
                      </Badge>
                    }
                  />
                  <Text size={200}>{agent.description}</Text>
                </Card>
              ))}
          </div>
        )}
      </div>

    </div>
  );
}
