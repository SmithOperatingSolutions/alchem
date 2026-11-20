use std::{fs, os::unix::fs::PermissionsExt, process::Command};

#[test]
fn cli_rejects_bad_arguments_and_preserves_output_on_invalid_ir() {
    let dir = std::env::temp_dir().join(format!("alchem-rust-cli-{}", std::process::id()));
    fs::create_dir(&dir).unwrap();
    let output = dir.join("program");
    let compiler = env!("CARGO_BIN_EXE_alchem-native-rust");
    for args in [
        vec![],
        vec!["--unknown"],
        vec!["--input"],
        vec!["--target", "other"],
        vec!["unexpected"],
    ] {
        let result = Command::new(compiler).args(args).output().unwrap();
        assert!(!result.status.success());
        assert!(String::from_utf8_lossy(&result.stderr).contains("E_"));
        assert!(!output.exists());
    }
    let input = dir.join("input.json");
    fs::write(
        &input,
        include_bytes!("../../../fixtures/ir/return-42.json"),
    )
    .unwrap();
    let args = [
        "--target",
        "x86_64-unknown-linux-gnu",
        "--input",
        input.to_str().unwrap(),
        "--output",
        output.to_str().unwrap(),
    ];
    let result = Command::new(compiler)
        .args(args)
        .arg("extra")
        .output()
        .unwrap();
    assert!(!result.status.success());
    assert!(!output.exists());
    let result = Command::new(compiler).args(args).output().unwrap();
    assert!(result.status.success(), "{:?}", result);
    assert_eq!(
        fs::metadata(&output).unwrap().permissions().mode() & 0o777,
        0o700
    );
    assert_eq!(Command::new(&output).status().unwrap().code(), Some(42));
    let before = fs::read(&output).unwrap();
    fs::write(&input, b"{").unwrap();
    assert!(!Command::new(compiler)
        .args(args)
        .output()
        .unwrap()
        .status
        .success());
    assert_eq!(fs::read(&output).unwrap(), before);
    assert_eq!(fs::read_dir(&dir).unwrap().count(), 2);
    fs::remove_dir_all(dir).unwrap();
}

#[test]
fn source_mode_requires_an_existing_frontend_and_preserves_output() {
    let dir = std::env::temp_dir().join(format!("alchem-rust-source-{}", std::process::id()));
    fs::create_dir(&dir).unwrap();
    let output = dir.join("program");
    fs::write(&output, b"existing output").unwrap();
    let result = Command::new(env!("CARGO_BIN_EXE_alchem-native-rust"))
        .args(["--source", "../../examples/invoice.alc", "--frontend"])
        .arg(dir.join("missing-frontend"))
        .arg("--output")
        .arg(&output)
        .output()
        .unwrap();
    assert!(!result.status.success());
    assert!(
        String::from_utf8_lossy(&result.stderr).starts_with("E_IO:"),
        "{:?}",
        result
    );
    assert_eq!(fs::read(&output).unwrap(), b"existing output");
    fs::remove_dir_all(dir).unwrap();
}
