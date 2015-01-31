# p4-whodunit
A python script to display who changed each line of code in a perforce depot file.

It is useful for tracking down recent changes that might have caused a problem.

#### Acknowledgements
The script was inspired by a shell script developed by my colleague: Kris Kozminski to combine the “`p4 describe`” and “`p4 annotate`” commands.

#### Running the Tool
You run the tool on a set of 1 or more perforce depot files. For each file it outputs information about each line of the file. Here is an example the shows two lines. 

```
$ p4-whodunit.py //depot/dev/proj1/lib1/src/file1.cc
  .
  .
  275 11547@bigbob                      |    auto up1 = make_unique(Thing);
    - 11547@bigbob ... 363442@jlinoff   -
# ^   ^     ^      ^   ^                ^    ^
# |   |     |      |   |                |    +--- col 6 - source line
# |   |     |      |   |                +-------- col 5 -separator (|, -)
# |   |     |      |   +------------------------- col 4 - who deleted it
# |   |     |      +----------------------------- col 3 - ellipses
# |   +------------------------------------------ col 2 - who deleted it
# +---------------------------------------------- col 1 - line number or dash (deleted)
```
The first one is currently present in the file. It was created by bigbob. The second one has been deleted. It was created by bigbob and deleted by jlinoff.

#### Format
The format of the output is each line of the file. The first column is the line number. The second column is the changelist and person (`@`) that created the line. The third column is an ellipse (`…`) if there is a fourth column. The fourth column is the changelist and name of who deleted the line. The fifth column is the separator (“`|`” line is present, “`-`” line was deleted). The sixth column is the text of the line.

#### Use Patterns
You can use the tool in conjunction with other tools like grep to find information about a specific line. Here is an example:

```
$ p4-whodunit.py //depot/dev/proj1/lib1/src/file1.cc | grep -B 2 -A 5 'make_unique'
```

Note that you do not have to specify the absolute depot path. If you are in a sandbox you can specify the relative path. Here is an example:

```
$ p4-whodunit.py proj1/lib1/src/file1.cc | grep -B 2 -A 5 'make_unique'
```
