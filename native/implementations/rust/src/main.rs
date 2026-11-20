use std::{
    env,
    fs::{self, OpenOptions},
    io::Write,
    os::unix::fs::{OpenOptionsExt, PermissionsExt},
    path::Path,
    process::Command,
};

fn io_error(error: std::io::Error) -> String {
    format!("E_IO: {error}")
}
fn run() -> Result<(), String> {
    let mut target = None;
    let mut input = None;
    let mut output = None;
    let mut source = None;
    let mut frontend = None;
    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        let (key, inline) = match arg.split_once('=') {
            Some((key, value)) => (key, Some(value.to_owned())),
            None => (arg.as_str(), None),
        };
        let slot = match key {
            "--target" | "-target" => &mut target,
            "--input" | "-input" => &mut input,
            "--output" | "-output" => &mut output,
            "--source" => &mut source,
            "--frontend" => &mut frontend,
            _ => return Err(format!("E_INVALID_ARGUMENT: unexpected argument {arg}")),
        };
        *slot = Some(
            inline
                .or_else(|| args.next())
                .ok_or_else(|| format!("E_INVALID_ARGUMENT: missing value for {key}"))?,
        );
    }
    if input.is_some() == source.is_some() {
        return Err("E_INVALID_ARGUMENT: exactly one of input/source is required".into());
    }
    if source.is_none() && frontend.is_some() {
        return Err("E_INVALID_ARGUMENT: frontend requires source mode".into());
    }
    if source.is_some() && target.is_none() {
        target = Some("x86_64-unknown-linux-gnu".into());
    }
    if target.as_deref() != Some("x86_64-unknown-linux-gnu") {
        return Err("E_UNSUPPORTED: target must be x86_64-unknown-linux-gnu".into());
    }
    let output = output
        .filter(|s| !s.is_empty())
        .ok_or("E_INVALID_ARGUMENT: output is required")?;
    let data = if let Some(source) = source {
        if source.is_empty() {
            return Err("E_INVALID_ARGUMENT: source is required".into());
        }
        if let (Ok(source_path), Ok(output_path)) =
            (fs::canonicalize(&source), fs::canonicalize(&output))
        {
            if source_path == output_path {
                return Err("E_INVALID_ARGUMENT: output must not overwrite source".into());
            }
        }
        let frontend = match frontend {
            Some(path) => std::path::PathBuf::from(path),
            None => env::current_exe()
                .map_err(io_error)?
                .with_file_name("alchem-source-probe"),
        };
        let result = Command::new(frontend)
            .args(["--input", &source, "--program"])
            .output()
            .map_err(io_error)?;
        if !result.status.success() {
            return Err(format!(
                "E_SOURCE: frontend rejected source: {}",
                String::from_utf8_lossy(&result.stderr).trim()
            ));
        }
        result.stdout
    } else {
        let input = input
            .filter(|s| !s.is_empty())
            .ok_or("E_INVALID_ARGUMENT: input is required")?;
        fs::read(input).map_err(io_error)?
    };
    let bytes = alchem_native_rust::compile(&data)?;
    let path = Path::new(&output);
    let dir = path
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    // create_new prevents following an existing temporary file or symlink.
    for sequence in 0..1000 {
        let temp = dir.join(format!(".alchem-native-{}-{sequence}", std::process::id()));
        let mut file = match OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&temp)
        {
            Ok(file) => file,
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(error) => return Err(io_error(error)),
        };
        let result = (|| {
            file.write_all(&bytes).map_err(io_error)?;
            file.set_permissions(fs::Permissions::from_mode(0o700))
                .map_err(io_error)?;
            drop(file);
            fs::rename(&temp, path).map_err(io_error)
        })();
        let _ = fs::remove_file(&temp);
        return result;
    }
    Err("E_IO: could not create temporary output".into())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
