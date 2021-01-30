# kahmi-build

Kahmi is a build system that is heavily inspired by Gradle implemented in Python. The main focus
is on ease-of-use.

## Quickstart (Haskell)

```
$ cat Main.hs
main = putStrLn "Hello, world!"

$ cat build.kmi
apply("lang.haskell")
haskellApplication {
  srcs = ["Main.hs"]
}

$ kahmi :run
Hello, World!
```

---

<p align="center">Copyright &copy; 2021 Niklas Rosenstein</p>
