/**
 * New project form — animated with path validation feedback.
 */
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert } from '@/components/ui/alert';
import { FolderPlus, CircleCheck, CircleX, Loader2 } from 'lucide-react';
import { PageWrapper, FadeIn, motion, springSmooth } from '@/components/motion';

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [codePath, setCodePath] = useState('');
  const [reqPath, setReqPath] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [codePathValid, setCodePathValid] = useState<boolean | null>(null);
  const [reqPathValid, setReqPathValid] = useState<boolean | null>(null);

  const validatePath = async (path: string, setter: (v: boolean | null) => void) => {
    if (!path.trim()) { setter(null); return; }
    try {
      const result = await api.validatePath(path);
      setter(result.exists);
    } catch { setter(null); }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const project = await api.createProject({ name, code_path: codePath, requirements_path: reqPath });
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageWrapper className="p-8 max-w-2xl mx-auto">
      <FadeIn>
        <div className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">New Project</h1>
          <p className="text-sm text-muted-foreground mt-1">Register a codebase and its requirements document.</p>
        </div>
      </FadeIn>

      <FadeIn delay={0.1}>
        <motion.div whileHover={{ y: -1 }} transition={{ duration: 0.2 }}>
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2"><FolderPlus className="h-4 w-4" />Project details</CardTitle>
              <CardDescription>Provide the project name and absolute filesystem paths.</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-5">
                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15, ...springSmooth }} className="space-y-2">
                  <Label htmlFor="name">Project name</Label>
                  <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="my-project" required className="font-mono text-sm" />
                  <p className="text-xs text-muted-foreground/60">Must be unique across all projects.</p>
                </motion.div>

                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, ...springSmooth }} className="space-y-2">
                  <Label htmlFor="code_path">Code directory</Label>
                  <div className="relative">
                    <Input id="code_path" value={codePath} onChange={(e) => { setCodePath(e.target.value); setCodePathValid(null); }} onBlur={() => validatePath(codePath, setCodePathValid)} placeholder="/absolute/path/to/code" required className="font-mono text-sm pr-9" />
                    <PathValidationIcon valid={codePathValid} />
                  </div>
                  <p className="text-xs text-muted-foreground/60">Absolute path to the source code directory.</p>
                </motion.div>

                <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25, ...springSmooth }} className="space-y-2">
                  <Label htmlFor="req_path">Requirements document</Label>
                  <div className="relative">
                    <Input id="req_path" value={reqPath} onChange={(e) => { setReqPath(e.target.value); setReqPathValid(null); }} onBlur={() => validatePath(reqPath, setReqPathValid)} placeholder="/absolute/path/to/requirements.md" required className="font-mono text-sm pr-9" />
                    <PathValidationIcon valid={reqPathValid} />
                  </div>
                  <p className="text-xs text-muted-foreground/60">Absolute path to the requirements Markdown file.</p>
                </motion.div>

                {error && (
                  <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
                    <Alert variant="destructive" className="text-sm">{error}</Alert>
                  </motion.div>
                )}

                <motion.div whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}>
                  <Button type="submit" disabled={loading} className="w-full">
                    {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Creating...</> : 'Create project'}
                  </Button>
                </motion.div>
              </form>
            </CardContent>
          </Card>
        </motion.div>
      </FadeIn>
    </PageWrapper>
  );
}

function PathValidationIcon({ valid }: { valid: boolean | null }) {
  if (valid === null) return null;
  return (
    <motion.div initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 15 }} className="absolute right-2.5 top-1/2 -translate-y-1/2">
      {valid ? <CircleCheck className="h-4 w-4 text-emerald-500" /> : <CircleX className="h-4 w-4 text-rose-500" />}
    </motion.div>
  );
}
