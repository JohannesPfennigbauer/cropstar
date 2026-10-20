---
status: accepted
---

# Operations are stored per Plot, grouped under one Task

Work such as "harrow plots 3, 4 and 5" is one Task with an Operation Type. That Task holds
one Operation per Plot, and each Operation has its own Status, Planned Details and Actual
Details. The Task's Status is derived from its Operations. We chose this so that the
Operation Log of every Plot is complete on its own for reports and as model input, while
the farmer can still create and complete the work in one step and finish it partially. We
rejected two alternatives. One Task carrying a list of Plots cannot record different
actual amounts or dates per Plot. Making each Operation an independent Task would need an
extra grouping concept just to show "2 of 3 done".
