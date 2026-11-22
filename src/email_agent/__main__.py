from importlib.metadata import version


def main() -> None:
    print(f"email-agent {version('email-agent')} starting")


if __name__ == "__main__":
    main()
