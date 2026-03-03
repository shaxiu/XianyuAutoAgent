"use client";

import { useEffect, useState } from "react";
import { AccountSelector } from "@/components/account-selector";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type Message = {
  id: string;
  chat_id: string;
  item_id: string;
  item_title: string;
  role: string;
  content: string;
  intent: string | null;
  created_at: string;
};

type ChatGroup = {
  chat_id: string;
  item_title: string;
  messages: Message[];
  lastTime: string;
};

export default function ConversationsPage() {
  const [accountId, setAccountId] = useState("");
  const [chatGroups, setChatGroups] = useState<ChatGroup[]>([]);
  const [selectedChat, setSelectedChat] = useState<string | null>(null);

  useEffect(() => {
    if (!accountId) return;
    fetch(`/api/conversations?account_id=${accountId}&limit=500`)
      .then((r) => r.json())
      .then((data: Message[]) => {
        if (!Array.isArray(data)) return;
        const groups: Record<string, ChatGroup> = {};
        const sorted = [...data].reverse();
        sorted.forEach((msg) => {
          if (!groups[msg.chat_id]) {
            groups[msg.chat_id] = {
              chat_id: msg.chat_id,
              item_title: msg.item_title || msg.item_id,
              messages: [],
              lastTime: msg.created_at,
            };
          }
          groups[msg.chat_id].messages.push(msg);
          groups[msg.chat_id].lastTime = msg.created_at;
        });
        const sortedGroups = Object.values(groups).sort(
          (a, b) => new Date(b.lastTime).getTime() - new Date(a.lastTime).getTime()
        );
        setChatGroups(sortedGroups);
      });
  }, [accountId]);

  const activeChat = chatGroups.find((g) => g.chat_id === selectedChat);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Conversations</h1>
        <AccountSelector value={accountId} onChange={setAccountId} />
      </div>

      <div className="grid grid-cols-3 gap-4" style={{ minHeight: "70vh" }}>
        <div className="col-span-1 space-y-2 overflow-y-auto max-h-[70vh]">
          {chatGroups.map((group) => (
            <Card
              key={group.chat_id}
              className={`cursor-pointer hover:bg-gray-50 ${
                selectedChat === group.chat_id ? "ring-2 ring-blue-500" : ""
              }`}
              onClick={() => setSelectedChat(group.chat_id)}
            >
              <CardContent className="p-3">
                <p className="font-medium text-sm truncate">{group.item_title}</p>
                <p className="text-xs text-gray-500">
                  {group.messages.length} messages
                </p>
                <p className="text-xs text-gray-400">
                  {new Date(group.lastTime).toLocaleString("zh-CN")}
                </p>
              </CardContent>
            </Card>
          ))}
          {chatGroups.length === 0 && accountId && (
            <p className="text-gray-400 text-sm">No conversations</p>
          )}
        </div>

        <div className="col-span-2 overflow-y-auto max-h-[70vh]">
          {activeChat ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{activeChat.item_title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {activeChat.messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`flex ${
                      msg.role === "assistant" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`max-w-[70%] rounded-lg px-3 py-2 ${
                        msg.role === "assistant"
                          ? "bg-blue-500 text-white"
                          : "bg-gray-100"
                      }`}
                    >
                      <p className="text-sm">{msg.content}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs opacity-60">
                          {new Date(msg.created_at).toLocaleTimeString("zh-CN")}
                        </span>
                        {msg.intent && (
                          <Badge variant="outline" className="text-xs">
                            {msg.intent}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              Select a conversation
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
