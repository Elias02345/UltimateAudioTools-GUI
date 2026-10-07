use minisign_verify::{PublicKey, Signature};
use std::{env, fs::File, io::Read, path::Path};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = env::args().collect();
    if args.len() != 4 {
        return Err("Usage: separator-artifact-verifier PUBLIC_KEY SIGNATURE ARTIFACT".into());
    }
    let key = PublicKey::from_file(Path::new(&args[1]))?;
    let signature = Signature::from_file(Path::new(&args[2]))?;
    let mut verifier = key.verify_stream(&signature)?;
    let mut file = File::open(&args[3])?;
    let mut buffer = [0u8; 65536];
    loop {
        let count = file.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        verifier.update(&buffer[..count]);
    }
    verifier.finalize()?;
    println!("SIGNATURE VERIFIED: {}", args[3]);
    Ok(())
}
