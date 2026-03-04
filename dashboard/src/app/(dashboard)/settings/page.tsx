"use client";

import { useEffect, useState } from "react";
import { AccountSelector } from "@/components/account-selector";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type AccountConfig = {
  id: string;
  name: string;
  cookies_str: string;
  api_key: string;
  model_base_url: string;
  model_name: string;
};

type Prompt = {
  type: string;
  content: string;
};

const PROMPT_TYPES = ["classify", "price", "tech", "default"] as const;

export default function SettingsPage() {
  const [accountId, setAccountId] = useState("");
  const [config, setConfig] = useState<AccountConfig | null>(null);
  const [prompts, setPrompts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!accountId) return;
    fetch(`/api/settings?account_id=${accountId}`)
      .then((r) => r.json())
      .then(setConfig);
    fetch(`/api/settings/prompts?account_id=${accountId}`)
      .then((r) => r.json())
      .then((data: Prompt[]) => {
        if (!Array.isArray(data)) return;
        const map: Record<string, string> = {};
        data.forEach((p) => (map[p.type] = p.content));
        setPrompts(map);
      });
  }, [accountId]);

  async function saveConfig() {
    if (!config) return;
    setSaving(true);
    setMessage("");
    const res = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        account_id: accountId,
        name: config.name,
        cookies_str: config.cookies_str,
        api_key: config.api_key,
        model_base_url: config.model_base_url,
        model_name: config.model_name,
      }),
    });
    setSaving(false);
    setMessage(res.ok ? "Config saved" : "Save failed");
  }

  async function savePrompt(type: string) {
    setSaving(true);
    setMessage("");
    const res = await fetch("/api/settings/prompts", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        account_id: accountId,
        type,
        content: prompts[type] || "",
      }),
    });
    setSaving(false);
    setMessage(res.ok ? `${type} prompt saved` : "Save failed");
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Settings</h1>
        <AccountSelector value={accountId} onChange={setAccountId} />
      </div>

      {message && (
        <p className="text-sm text-green-600">{message}</p>
      )}

      {config && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Account Config</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Account Name</Label>
                <Input
                  value={config.name}
                  onChange={(e) => setConfig({ ...config, name: e.target.value })}
                  placeholder="e.g. My Shop"
                />
              </div>
              <div>
                <Label>API Key</Label>
                <Input
                  type="password"
                  value={config.api_key}
                  onChange={(e) => setConfig({ ...config, api_key: e.target.value })}
                />
              </div>
              <div>
                <Label>Model Base URL</Label>
                <Input
                  value={config.model_base_url}
                  onChange={(e) => setConfig({ ...config, model_base_url: e.target.value })}
                />
              </div>
              <div>
                <Label>Model Name</Label>
                <Input
                  value={config.model_name}
                  onChange={(e) => setConfig({ ...config, model_name: e.target.value })}
                />
              </div>
              <div>
                <Label>Cookies</Label>
                <Textarea
                  rows={3}
                  value={config.cookies_str}
                  onChange={(e) => setConfig({ ...config, cookies_str: e.target.value })}
                />
              </div>
              <Button onClick={saveConfig} disabled={saving}>
                {saving ? "Saving..." : "Save Config"}
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Prompts</CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="classify">
                <TabsList>
                  {PROMPT_TYPES.map((type) => (
                    <TabsTrigger key={type} value={type}>
                      {type}
                    </TabsTrigger>
                  ))}
                </TabsList>
                {PROMPT_TYPES.map((type) => (
                  <TabsContent key={type} value={type} className="space-y-3">
                    <Textarea
                      rows={15}
                      value={prompts[type] || ""}
                      onChange={(e) =>
                        setPrompts({ ...prompts, [type]: e.target.value })
                      }
                      placeholder={`Enter ${type} prompt...`}
                    />
                    <Button onClick={() => savePrompt(type)} disabled={saving}>
                      {saving ? "Saving..." : `Save ${type} Prompt`}
                    </Button>
                  </TabsContent>
                ))}
              </Tabs>
            </CardContent>
          </Card>
        </div>
      )}

      {!config && accountId && (
        <p className="text-gray-400">Loading config...</p>
      )}
      {!accountId && (
        <p className="text-gray-400">Select an account to configure</p>
      )}
    </div>
  );
}
