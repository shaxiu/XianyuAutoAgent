"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type Account = {
  id: string;
  name: string;
  status: string;
};

type Stats = {
  totalMessages: number;
  todayMessages: number;
  errorCount: number;
};

export default function DashboardPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [stats, setStats] = useState<Record<string, Stats>>({});

  useEffect(() => {
    fetch("/api/accounts")
      .then((r) => r.json())
      .then((data: Account[]) => {
        setAccounts(data);
        data.forEach((account) => {
          Promise.all([
            fetch(`/api/conversations?account_id=${account.id}&limit=1000`).then((r) => r.json()),
            fetch(`/api/logs?account_id=${account.id}&level=ERROR&limit=100`).then((r) => r.json()),
          ]).then(([conversations, errors]) => {
            const today = new Date().toISOString().split("T")[0];
            const todayMsgs = Array.isArray(conversations)
              ? conversations.filter((c: any) => c.created_at?.startsWith(today))
              : [];
            setStats((prev) => ({
              ...prev,
              [account.id]: {
                totalMessages: Array.isArray(conversations) ? conversations.length : 0,
                todayMessages: todayMsgs.length,
                errorCount: Array.isArray(errors) ? errors.length : 0,
              },
            }));
          });
        });
      });
  }, []);

  function statusBadge(status: string) {
    switch (status) {
      case "online":
        return <Badge className="bg-green-500">Online</Badge>;
      case "error":
        return <Badge variant="destructive">Error</Badge>;
      default:
        return <Badge variant="secondary">Offline</Badge>;
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {accounts.map((account) => (
          <Card key={account.id}>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>{account.name}</CardTitle>
              {statusBadge(account.status)}
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-2xl font-bold">
                    {stats[account.id]?.totalMessages ?? "-"}
                  </p>
                  <p className="text-sm text-gray-500">Total Messages</p>
                </div>
                <div>
                  <p className="text-2xl font-bold">
                    {stats[account.id]?.todayMessages ?? "-"}
                  </p>
                  <p className="text-sm text-gray-500">Today</p>
                </div>
                <div>
                  <p className="text-2xl font-bold text-red-500">
                    {stats[account.id]?.errorCount ?? "-"}
                  </p>
                  <p className="text-sm text-gray-500">Errors</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
