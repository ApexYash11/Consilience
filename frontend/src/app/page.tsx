import { Shell } from "@/components/layout";
import { Button, Card, Input } from "@/components/ui";

export default function Home() {
  return (
    <Shell>
      <div className="mx-auto grid w-full max-w-[980px] gap-4 md:grid-cols-2">
        <Card>
          <h1
            className="mb-1 text-[28px]"
            style={{ fontFamily: "var(--font-display)", fontWeight: 400, lineHeight: 1.2 }}
          >
            Frontend Started
          </h1>
          <p className="mb-4 text-[var(--text-secondary)]">
            Phase 0 foundations are in place. Continue by building auth pages and research flows.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button>Primary Action</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="upgrade">Upgrade</Button>
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 text-xl font-medium">Create Research</h2>
          <div className="space-y-3">
            <Input
              label="Research Topic"
              placeholder="What would you like to research?"
              helperText="Minimum 10 characters"
            />
            <Input label="Budget Limit" placeholder="$0.10" error="Optional: use numeric format" />
            <div className="flex gap-2">
              <Button size="lg">Start Research</Button>
              <Button size="lg" variant="ghost">
                Save Draft
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </Shell>
  );
}
