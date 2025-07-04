export interface ProcessedEvent {
  title: string;
  data: string;
}

interface ActivityTimelineProps {
  events: ProcessedEvent[];
}

export function ActivityTimeline({ events }: ActivityTimelineProps) {
  return (
    <div className="space-y-4">
      {events.map((event, index) => (
        <div key={index} className="flex items-start">
          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-neutral-700 flex items-center justify-center mr-4">
            <div className="w-2 h-2 bg-neutral-400 rounded-full"></div>
          </div>
          <div className="flex-grow">
            <h3 className="font-semibold text-sm text-neutral-100">
              {event.title}
            </h3>
            <p className="text-sm text-neutral-400">{event.data}</p>
          </div>
        </div>
      ))}
      <div className="flex items-start">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-neutral-700 flex items-center justify-center mr-4">
          <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
        </div>
        <div className="flex-grow">
          <h3 className="font-semibold text-sm text-neutral-100">
            Thinking...
          </h3>
        </div>
      </div>
    </div>
  );
}
