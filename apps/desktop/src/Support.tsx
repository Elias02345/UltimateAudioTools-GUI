import { Coffee, Copy, ExternalLink, Github } from "lucide-react";
import { openUrl } from "@tauri-apps/plugin-opener";

export const DONATIONS = [
  {
    name: "Bitcoin",
    network: "Bitcoin (BTC)",
    address: "bc1qphk3h7sw6j429c62ypw6zxgmkfeevmxs437ze3",
  },
  {
    name: "Ethereum",
    network: "Ethereum (ETH)",
    address: "0x81deF905D66fd17433003e749f1e69bCFd95664d",
  },
  {
    name: "Solana",
    network: "Solana (SOL)",
    address: "G362aMnx7jSXp4iWtCwyw2yXy52ukRVoFgYCpw4aqrPQ",
  },
] as const;
export const PAYPAL = "https://www.paypal.com/paypalme/EliasK09";
export const CONTRIBUTOR = "https://github.com/Elias02345";

export function Support({
  notify,
  onError,
}: {
  notify: (message: string) => void;
  onError: (error: unknown) => void;
}) {
  return (
    <section className="support-view">
      <div className="page-heading">
        <div>
          <h1>Enjoying Separator?</h1>
          <p>
            A coffee or a donation helps me keep building and improving the app.
          </p>
        </div>
        <Coffee size={28} />
      </div>
      <p>
        Thank you for supporting independent development. Donations are
        optional; every feature stays available to everyone.
      </p>
      <div className="support-paypal">
        <h2>Buy me a coffee</h2>
        <p>Choose any amount on PayPal.</p>
        <button
          className="primary"
          onClick={() => void openUrl(PAYPAL).catch(onError)}
        >
          <Coffee size={17} /> Donate with PayPal <ExternalLink size={15} />
        </button>
      </div>
      <h2>Or donate with crypto</h2>
      <p className="muted">Use the network shown for each address.</p>
      <div className="donation-list">
        {DONATIONS.map(({ name, network, address }) => (
          <div className="donation-row" key={name}>
            <div>
              <strong>{name}</strong>
              <small>{network}</small>
              <code>{address}</code>
            </div>
            <button
              aria-label={`Copy ${name} address`}
              onClick={() =>
                void navigator.clipboard
                  .writeText(address)
                  .then(() => notify(`${name} address copied.`))
                  .catch(onError)
              }
            >
              <Copy size={15} /> Copy address
            </button>
          </div>
        ))}
      </div>
      <div className="support-credit">
        <h2>I'm Elias</h2>
        <p>I created Separator and continue to maintain and improve it.</p>
        <button onClick={() => void openUrl(CONTRIBUTOR).catch(onError)}>
          <Github size={16} /> @Elias02345 <ExternalLink size={14} />
        </button>
      </div>
    </section>
  );
}
