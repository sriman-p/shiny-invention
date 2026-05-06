'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [codePath, setCodePath] = useState('');
  const [reqPath, setReqPath] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const project = await api.createProject({
        name,
        code_path: codePath,
        requirements_path: reqPath,
      });
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-semibold tracking-tight mb-6">New Project</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Project details</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="my-project"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="code_path">Code path</Label>
              <Input
                id="code_path"
                value={codePath}
                onChange={(e) => setCodePath(e.target.value)}
                placeholder="/absolute/path/to/code"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="req_path">Requirements path</Label>
              <Input
                id="req_path"
                value={reqPath}
                onChange={(e) => setReqPath(e.target.value)}
                placeholder="/absolute/path/to/requirements.md"
                required
              />
            </div>
            {error && <p className="text-sm text-rose-600">{error}</p>}
            <Button type="submit" disabled={loading}>
              {loading ? 'Creating...' : 'Create project'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
