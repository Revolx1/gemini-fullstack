import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ArrowUpIcon, StopIcon } from "@radix-ui/react-icons";
import { useState } from "react";

interface WelcomeScreenProps {
  handleSubmit: (query: string, effort: string, model: string) => void;
  isLoading: boolean;
  onCancel: () => void;
}

export function WelcomeScreen({
  handleSubmit,
  isLoading,
  onCancel,
}: WelcomeScreenProps) {
  const [query, setQuery] = useState("");
  const [effort, setEffort] = useState("low");
  const [model, setModel] = useState("gemini-1.5-pro-latest");

  const handleTextareaKeyDown = (
    e: React.KeyboardEvent<HTMLTextAreaElement>
  ) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading) {
        handleSubmit(query, effort, model);
      }
    }
  };

  const handleEffortChange = (value: string) => {
    setEffort(value);
  };

  const handleModelChange = (value: string) => {
    setModel(value);
  };

  return (
    <div className="flex flex-col items-center justify-center h-full bg-neutral-800 text-neutral-100">
      <div className="w-full max-w-2xl px-4">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold tracking-tight">
            Professional Research Agent
          </h1>
          <p className="text-lg text-neutral-400 mt-2">
            Your AI-powered research assistant
          </p>
        </div>

        <div className="bg-neutral-900 border border-neutral-700 rounded-lg p-1.5">
          <div className="relative">
            <Textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleTextareaKeyDown}
              placeholder="What topic do you want to research?"
              className="w-full h-24 bg-transparent border-0 text-base text-neutral-100 placeholder-neutral-500 resize-none focus:outline-none focus:ring-0"
              disabled={isLoading}
            />
            {isLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-neutral-900 bg-opacity-80 rounded-lg">
                <div className="flex items-center space-x-2">
                  <div className="h-2 w-2 bg-neutral-400 rounded-full animate-pulse [animation-delay:-0.3s]"></div>
                  <div className="h-2 w-2 bg-neutral-400 rounded-full animate-pulse [animation-delay:-0.15s]"></div>
                  <div className="h-2 w-2 bg-neutral-400 rounded-full animate-pulse"></div>
                </div>
              </div>
            )}
          </div>
          <div className="flex items-center justify-between p-2">
            <div className="flex items-center space-x-2">
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
                Cancel
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={() => handleSubmit(query, effort, model)}
                disabled={!query.trim()}
                className="h-8"
              >
                <ArrowUpIcon className="mr-1" />
                Submit
              </Button>
            )}
          </div>
        </div>

        <div className="text-center mt-8 text-xs text-neutral-500">
          This is a research agent powered by LangGraph. It can perform web
          searches and generate comprehensive reports on a given topic.
        </div>
      </div>
    </div>
  );
}