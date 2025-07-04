import type { Message } from "@langchain/langgraph-sdk";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  ArrowUpIcon,
  PlusIcon,
  ReloadIcon,
  StopIcon,
} from "@radix-ui/react-icons";
import {
  ActivityTimeline,
  ProcessedEvent,
} from "@/components/ActivityTimeline";
import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import { ScrollArea } from "./ui/scroll-area";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface ChatMessagesViewProps {
  messages: Message[];
  isLoading: boolean;
  scrollAreaRef: React.RefObject<HTMLDivElement | null>;
  onSubmit: (query: string, effort: string, model: string) => void;
  onCancel: () => void;
  liveActivityEvents: ProcessedEvent[];
  historicalActivities: Record<string, ProcessedEvent[]>;
}

export function ChatMessagesView({
  messages,
  isLoading,
  scrollAreaRef,
  onSubmit,
  onCancel,
  liveActivityEvents,
  historicalActivities,
}: ChatMessagesViewProps) {
  const [query, setQuery] = useState("");
  const [effort, setEffort] = useState("low");
  const [model, setModel] = useState("gemini-1.5-pro-latest");

  const handleTextareaKeyDown = (
    e: React.KeyboardEvent<HTMLTextAreaElement>
  ) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading) {
        onSubmit(query, effort, model);
        setQuery("");
      }
    }
  };

  const handleEffortChange = (value: string) => {
    setEffort(value);
  };

  const handleModelChange = (value: string) => {
    setModel(value);
  };

  const isLastMessageLoading = isLoading && messages.length > 0;

  return (
    <div className="flex flex-col h-full">
      <div className="flex-grow overflow-y-auto">
        <ScrollArea className="h-full" ref={scrollAreaRef}>
          <div className="prose prose-lg max-w-none text-neutral-100 px-6 py-8">
            {messages.map((msg, index) => (
              <div
                key={msg.id || index}
                className="flex items-start gap-4 mb-8"
              >
                <Avatar className="w-8 h-8 border-2 border-neutral-700">
                  <AvatarImage
                    src={
                      msg.type === "human"
                        ? "https://placekitten.com/g/40/40"
                        : "/gemini.png"
                    }
                  />
                  <AvatarFallback>
                    {msg.type === "human" ? "U" : "A"}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <div className="font-bold text-sm mb-2">
                    {msg.type === "human" ? "You" : "Research Agent"}
                  </div>
                  <div className="prose prose-invert max-w-none">
                    <ReactMarkdown>{msg.content as string}</ReactMarkdown>
                  </div>
                  {msg.type === "ai" &&
                    (historicalActivities[msg.id!] || []).length > 0 && (
                      <div className="mt-4">
                        <ActivityTimeline
                          events={historicalActivities[msg.id!] || []}
                        />
                      </div>
                    )}
                </div>
              </div>
            ))}

            {isLastMessageLoading && (
              <div className="flex items-start gap-4 mb-8">
                <Avatar className="w-8 h-8 border-2 border-neutral-700">
                  <AvatarImage src="/gemini.png" />
                  <AvatarFallback>A</AvatarFallback>
                </Avatar>
                <div className="flex-1">
                  <div className="font-bold text-sm mb-2">Research Agent</div>
                  <div className="mt-4">
                    <ActivityTimeline events={liveActivityEvents} />
                  </div>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
      </div>

      <div className="px-6 py-4 border-t border-neutral-700">
        <div className="bg-neutral-900 border border-neutral-700 rounded-lg p-1.5">
          <div className="relative">
            <Textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleTextareaKeyDown}
              placeholder="What topic do you want to research?"
              className="w-full bg-transparent border-0 text-base text-neutral-100 placeholder-neutral-500 resize-none focus:outline-none focus:ring-0"
              disabled={isLoading}
            />
          </div>
          <div className="flex items-center justify-between p-2">
            <div className="flex items-center space-x-2">
              <Button variant="outline" size="sm" className="h-8">
                <PlusIcon />
              </Button>
              <Select
                value={effort}
                onValueChange={handleEffortChange}
                disabled={isLoading}
              >
                <SelectTrigger className="w-auto bg-neutral-800 border-neutral-700 h-8 text-xs">
                  <SelectValue placeholder="Effort" />
                </SelectTrigger>
                <SelectContent className="bg-neutral-800 text-neutral-100 border-neutral-700">
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                </SelectContent>
              </Select>
              <Select
                value={model}
                onValueChange={handleModelChange}
                disabled={isLoading}
              >
                <SelectTrigger className="w-auto bg-neutral-800 border-neutral-700 h-8 text-xs">
                  <SelectValue placeholder="Model" />
                </SelectTrigger>
                <SelectContent className="bg-neutral-800 text-neutral-100 border-neutral-700">
                  <SelectItem value="gemini-1.5-pro-latest">
                    gemini-1.5-pro-latest
                  </SelectItem>
                  <SelectItem value="gemini-1.5-flash-latest">
                    gemini-1.5-flash-latest
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            {isLoading ? (
              <Button
                variant="destructive"
                size="sm"
                onClick={onCancel}
                className="h-8"
              >
                <StopIcon className="mr-1" />
                Stop
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={() => {
                  onSubmit(query, effort, model);
                  setQuery("");
                }}
                disabled={!query.trim()}
                className="h-8"
              >
                <ArrowUpIcon className="mr-1" />
                Submit
              </Button>
            )}
          </div>
        </div>
        <div className="text-center mt-2 text-xs text-neutral-500">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => window.location.reload()}
            className="text-xs"
          >
            <ReloadIcon className="mr-1" />
            New Research
          </Button>
        </div>
      </div>
    </div>
  );
}
