# Ripple Radar user guide

This guide explains every page and every button in Ripple Radar. It is written so anyone can follow it, even on their first day.

---

## 1. What Ripple Radar does, in one minute

Wacky Wheels builds cars in six factories (we call them **plants**). The plants do not keep spare parts on the shelf. Parts arrive just in time, by truck, from about 20 **suppliers**.

That means one small problem can spread fast:

- A truck of batteries is late.
- So the plant cannot build some cars on those days.
- So customers who ordered those cars will get them later.
- So their **dealers** (the shops that sell the cars) need to be told.
- And some customers should get a **loaner car** while they wait.

We call this spreading problem a **ripple**.

Every day, people send messages about problems: emails from suppliers, alerts from plants, chat messages, quality warnings. Some are serious, some are rumors, and some have nothing to do with us.

**Ripple Radar reads each message, figures out what it means, finds everything it affects, fixes what can be fixed, and tells the right people.** It follows the company rulebook every time, and it runs entirely on this computer, so nothing leaves the building.

Your job is to watch what it did, step in when it asks for a person, and send it new messages when they arrive.

---

## 2. Words you will see

| Word               | What it means                                                                                                        |
| ------------------ | -------------------------------------------------------------------------------------------------------------------- |
| **Plant**          | A car factory. We have six: San Antonio, Lexington, Jackson, Princeton, Huntsville and Greensboro.                   |
| **Supplier**       | A company that makes parts for us, like batteries, chips or seats.                                                   |
| **Shipment**       | One delivery of parts from a supplier to a plant.                                                                    |
| **Part**           | A piece that goes into a car, like a 60 kWh battery pack or an infotainment chip.                                    |
| **Model**          | A type of car we make: Pioneer, Summit, Ranger, Nova, Terra and Voyager.                                             |
| **Build**          | One planned batch of cars at a plant on a certain day. Also called a production order.                               |
| **Customer order** | A car a customer has already ordered and is waiting for.                                                             |
| **Dealer**         | A shop that sells our cars and talks to the customer.                                                                |
| **Loaner car**     | A car we lend to a customer while theirs is delayed. Platinum and Gold customers get one first.                      |
| **Lot**            | A batch of the same part, made at the same time. If one part in a lot is bad, the whole lot is suspect.              |
| **Quality hold**   | Putting a bad lot on pause, stopping sale of unsold cars that have it, and contacting owners who already bought one. |
| **Incident**       | A message that turned out to be a real problem we acted on.                                                          |
| **Ripple**         | Everything one problem touches: builds, orders, dealers and customers.                                               |
| **Noise**          | A message that is not about our operations, like a request for a brochure.                                           |
| **Needs review** | A message that might be real but is too vague to act on safely. A human has to decide.                               |

---

## 3. Getting around

### The sidebar (left side)

The sidebar is how you move between pages. Click any name to go there. The page you are on is highlighted in green.

| Page | Use it when you want to... |
|---|---|
| **Operations** | See what is happening right now. This is the home page. |
| **Incidents** | Look at one problem in full detail. |
| **Supply network** | Look up a customer, order, car, lot or plant and see what it is connected to. |
| **Analytics** | See the whole day on one screen. |
| **Evidence** | Prove what was done, for a manager or an auditor. |
| **Simulation** | Triage training with the real messages. |
| **Help** | Read a short version of this guide or replay the tour. |

### The top bar

- **Wacky Wheels Co.**: the company you are working for.
- **The model button** (it shows a green dot and a name like "Qwen2.5 · 3B Local"): this is the small AI that reads messages. A **green dot** means it is running. A **red dot** means it is off (see Troubleshooting). Click it to switch to another model installed on this computer.
- **New event**: click this when a new email, chat or alert comes in. See section 5.1.
- **The person icon**: your account.

---

## 4. Every page, explained

### 4.1 Operations (the home page)

**What it is for:** a quick look at the whole situation. Start every shift here.

**What you see:**

1. **Five number cards across the top**
   - **Events**: how many messages came in. Click it to see them all.
   - **Needs review**: how many are waiting for a person to decide. It turns amber when it is more than zero. Click it to see only those.
   - **Builds moved**: car builds moved to a new day or a new plant. Click it to see each move in the action log.
   - **Customers notified**: owners of affected cars who were contacted. Click it for the list.
   - **Loaners assigned**: loaner cars given to customers whose cars are late. Click it for the list.

   Click any card to see the details behind it.

2. **Supply chain ripple (the big picture in the middle)**
   This shows the ripple of the incident you have selected.
   - **The glowing circle in the middle** is the plant that was hit.
   - **On the left** is what caused the problem: the **supplier**, the **part** and the car **models** that use it.
   - **On the right** is who it reaches: the **builds** that had to move, the **dealers** who were told, and the **customers** who were affected.
   - Each bubble shows a number and a name. A faded bubble with "none" means that part of the ripple did not apply.
   - Click **Network** or **Map** at the top to switch views. **Map** shows the same ripple on a map of our plants and dealers.
   - Click **Open incident** to see every detail.

3. **Active incidents (the list on the right)**
   Every message that mattered, sorted so the ones that need you come first:
   - **Needs review** at the top. Start here.
   - **Ready, not sent yet** next. These are planned and checked but not carried out yet.
   - **Resolved** last. These are finished.

   Each one shows:
   - an ID like **E-10** and what kind of problem it is,
   - where it happened,
   - a colored label (see section 6).

   **Click any incident** to show its ripple in the middle. Click **View all** to go to the Incidents page.

**Good to know:** Messages that were just noise are not in this list. A small line at the bottom of the list tells you how many there were.

---

### 4.2 Incidents

**What it is for:** working on one problem in full detail. Use it when you need to understand exactly what happened and what was done.

The page has three columns.

**Left: the incident queue**

- At the top are counters: **Total**, **Review**, **Resolved** and **Ignored** (plus **Not sent** when something is waiting to be sent). Click one to show only those messages.
- Below is every message, in the order it arrived. Each row shows the time, the kind of problem, where it happened and its label.
- Click a row to open it.

**Middle: the selected incident**

1. **The message itself**, exactly as it was written. Some words are **highlighted in green**. These are the words the AI understood, like a plant name or a date. **Hover over a highlighted word** to see what it meant. For example, hovering over "next Friday" shows the real date, Mar 19.
2. **Decision**: one sentence saying what the tower decided.
3. **Three views** you can switch between:
   - **Impact map**: plays the ripple on the map. The late supplier's route appears as an amber dashed line. Then red lines spread from the plant to the dealers. When everything is handled, the dealers turn green. Click **Replay** to watch it again.
   - **Graph**: the same ripple as columns, from left to right: source, parts, models, builds, orders, then people.
   - **Recovery timeline**: the schedule before and after the fix. Each row is a plant, each column is a day, and each small box is one build.
     - **Striped red days** are days the plant could not build.
     - **Red boxes** are builds that were stuck.
     - It starts on **Before**, then moves the builds to their new days on its own. **Green boxes** were moved to a later day at the same plant. **Amber boxes** were moved to a different plant.
     - Click **Before** or **After recovery** to switch back and forth. **Click any box** and the matching action opens on the right with its evidence: where it was, where it is now, the rule it follows and whether the company systems accepted it.
4. **The bottom line** says the result in plain words, like "Done. All 42 actions were carried out and accepted by the company systems." or "Waiting for a person to decide. Nothing was changed."

**Right: Actions and Decision details**

- **Actions** has two parts:
  - **How the agents handled it**: the story of the incident, step by step. The Coordinator read the message. Each helper proposed its actions. The rulebook approved them in a rehearsal on a copy of the systems. Then the Coordinator sent them to the real company systems, and it says how many were accepted.
  - **Every action**, grouped by type. Click a group to open it, then **click any single action** to see its evidence right there: was and now (for moved builds), which helper proposed it, the rule it follows in plain words, whether the server accepted it, and the chain of records that led to it. A green tick on the right of an action means the company systems accepted it.
- **Decision details**: how the message was read, word by word, and which records it matched. If some customers did not get a loaner because the dealer ran out, it is listed here. You can also type any ID into **Trace any record** to see its full story.

**Good to know:** The tower has four helpers, and each has one job:

- the **Coordinator** reads the message and decides what kind it is;
- the **Supply Chain Planner** moves builds;
- **Dealer and Customer Care** tells dealers and assigns loaner cars;
- **Quality** handles bad parts.

---

### 4.3 Supply network

**What it is for:** answering questions like "why is this customer affected?" or "what is this lot connected to?". Think of it as a map of how everything in the company is linked.

**How to use it:**

1. Type into **Find a record** on the left. You can search for a customer (like **C1633**), a customer order (**CO-02638**), a build (**PO-0437**), a car (by its VIN), a lot (**LOT-0130**), a shipment (**SH-0248**), a dealer (**D25**) or a plant (**P_AL**).
2. Or click one of the **Start from** examples.
3. The record appears as a **big circle in the middle**. Everything directly connected to it sits around it. Under each name is a short note saying how it is connected, like "installed in", "made by" or "customer order".
4. **Click any circle around the edge** to move to it. This lets you follow the ripple one step at a time.
5. **Scroll** to zoom in and out, or use the **+**, **minus** and **circle** buttons in the corner. The circle button fits everything back on screen.
6. The **Record** panel on the right shows the facts about the selected item and **every action taken on it**, with a link to the incident that caused it.

**Colors:** each kind of record has its own color, listed at the bottom of the picture. A circle with a **thick green ring** means the tower took action on that record.

---

### 4.4 Analytics

**What it is for:** seeing the whole day on one screen, without reading any messages. Great for a manager, a shift handover or a meeting.

**What you see:**

1. **Numbers across the top**: messages, builds moved, order delays sent to dealers, loaner cars, lots held, cars stopped from sale, and owners contacted.
2. **Network impact (map)**: every plant, supplier and dealer that was involved today, all at once.
   - **Red dots with a ring** are plants that had a problem. Click one to open its incident.
   - **Amber dots** are suppliers that were late or sent bad parts. Suppliers far away are shown at the edge of the map with their city in brackets.
   - **Green dots** are dealers the tower reached. **Bigger dots** mean more of that dealer's customers were affected.
   - **Hover** over any dot for details.
3. **Event timeline**: a timeline from 7:00 to 11:30. Each bubble is one message, placed at the time it arrived.
   - Top row: messages the tower **acted on**.
   - Middle row: messages that **need review**.
   - Bottom row: messages that were **ignored**.
   - **Bigger bubbles** mean more actions were needed. Click a bubble to open it.
4. **Disruption calendar**: one row per plant and one column per working day. The green line marks **today**.
   - **Red blocks**: the plant was down.
   - **Amber blocks**: the plant was missing a part.
   - **Purple striped blocks**: cars already built with a bad part (these are in the past, to the left of today).
   - Each block shows its incident ID. Click it to open the incident.

**Making things bigger:** every section has an **expand button** (four little corners) in its top right. Click it to fill the screen. Click it again, or press **Esc**, to go back.

**Zooming the map:** scroll with your mouse, drag to move around, or use the **+**, **minus** and **circle** buttons. The circle button resets the view.

---

### 4.5 Evidence

**What it is for:** proving what was done and that the rules were followed. Use it when a manager, auditor or judge asks "how do we know this was done correctly?"

**What you see:**

1. **Execution summary**: the key totals. Two of them are worth understanding:
   - **Failed in rehearsal**: before anything is sent, every action is tried on a *copy* of the company systems. This should be 0.
   - **Executed on the server**: how many actions were then carried out on the *real* company systems and accepted. Rehearsal proves the plan is right; execution proves it was actually done.

   **Click a number** to filter the log below. For example, click **Escalated to a human** to see only those.
2. **Policy check matrix**: a grid with one row per message and one column per rule. A **green tick** means the rule applied and passed. A **dot** means that rule did not apply to that message. A **red cross** would mean a rule failed. Click a message ID to filter the log to it.
3. **Action log**: every action ever taken, one per row: which message caused it, which helper did it, what it did, to what, which rule it follows, whether it worked, and why. Use the drop-downs and the search box to narrow it down. Click an event ID to open that incident.

**Good to know:** Before anything is sent, the tower first practices every action on a copy of the company systems and checks all ten rules. Only if everything passes is it sent for real. This page is the record of that.

---

### 4.6 Simulation

**What it is for:** triage training with the 15 real messages from Monday morning. Good for a new teammate.

**How it works:**

1. Each scenario shows one message, just as it arrived.
2. Choose your decision:
   - **Act** (press **A**): a confirmed disruption.
   - **Escalate** (press **E**): possibly relevant, but unconfirmed or incomplete.
   - **Ignore** (press **I**): not related to operations.
3. You see your decision, what Ripple Radar did, and the policy result. For a real problem, the impact plays on the map.
4. Press **Enter** or **Next scenario** to continue.
5. At the end you see how many matched, by type, and how long you took.

---

### 4.7 Help

A short version of this guide:

- the three steps to get started;
- what each colored label means;
- the ten rules in plain English;
- system information, such as which AI model is running.

Click **Take the tour** to see the guided tour again.

---

## 5. How do I...?

### 5.1 ...send in a new message that just arrived?

1. Click **New event** in the top bar.
2. Paste or type the message exactly as you received it. Do not clean it up, because the tower is built to read messy messages.
3. Click **Analyze event**.
4. Wait a few seconds. You land on the Incidents page with the new message selected.
5. Look at the label:
   - **Not sent**: the plan is ready and passed every rule in rehearsal. The header says **Preview, not sent**. Nothing has changed yet.
   - **Resolved**: every action was carried out and accepted by the company systems. Check **Actions** if you are curious.
   - **Needs review**: a person must decide. See 5.2.
   - **Ignored**: nothing to do.

6. To carry out a plan that is **Not sent**, click **Send to enterprise server** at the bottom. Each action goes to the company systems once; the label turns **Resolved** when all are accepted, **Partial** if only some are, and **Failed** if none are (the reason is shown). A plan can only be sent once.

Not sure what to type? The window has example messages you can click to try.

### 5.2 ...deal with something marked "Needs review"?

1. Open it from **Operations** (the amber card) or from **Incidents**.
2. Read the message and the **Decision** line. It says what was missing, for example "doesn't say which part or when".
3. Contact the person who sent the message and ask for the missing details.
4. When you have them, send a new, clearer message with **New event**.

The tower never guesses, so nothing was changed while it waited for you.

### 5.3 ...answer "why is my car late?" from a customer or dealer?

1. Go to **Supply network**.
2. Type the customer ID or order number and press Enter.
3. Look at **Actions on this record** on the right. It lists what happened and why, in order, with a link to the incident.

### 5.4 ...give my manager a quick summary?

Open **Analytics** and share your screen. The top numbers, the map, the morning timeline and the calendar tell the whole story. Expand any section to make it bigger.

### 5.5 ...prove to an auditor that the rules were followed?

Open **Evidence**. Show the **Policy check matrix** (all green ticks), **Failed in rehearsal** (zero) and **Executed on the server** (all of them accepted). Use the action log filters to show any specific action; the **Server** column shows whether the real company systems accepted it.

---

## 6. What the colored labels mean

| Label | Meaning | What you should do |
|---|---|---|
| **Resolved** (green) | A real problem. Every action was carried out and accepted by the company systems. | Nothing. You can look at the details if you want. |
| **Not sent** (blue) | A real problem. The plan is ready and passed every rule in a rehearsal, but it has not been carried out on the company systems yet. | Have the system owner send it to the company systems. |
| **Needs review** (amber) | It might be real, but it is too vague or unconfirmed. Nothing was changed. | Find out the missing details and send a clearer message. |
| **Ignored** (grey) | Not about our plants, parts or quality. | Nothing. |
| **Blocked** (red) | The tower made a plan, but it did not pass a rule check, so nothing was sent. | Ask your supervisor or the system owner to look at it. |
| **Partial** (red) | Some actions were accepted by the company systems and some were not. | Ask the system owner to finish it. Do not send it again. |
| **Failed** (red) | The company systems refused every action, so nothing changed. | Read the reason on the incident and ask the system owner. |

---

## 7. The ten rules, in plain words

The tower follows the operations handbook. In short:

1. **Late part**: if a part is late, every build that needs it at that plant, between the old and new arrival dates, is affected.
2. **Plant down**: if a plant is down, every build there on those days is affected.
3. **Rescheduling**: move each build to the earliest free day at the same plant. Only if that plant is full, move it to another plant that makes the same model.
4. **Dealers**: each dealer gets exactly one update, listing only their delayed orders.
5. **Loaner cars**: Platinum customers first, then Gold, then whoever was promised their car soonest. Standard customers do not get one. Each dealer has a limited number.
6. **Quality hold**: hold the bad lot, stop sale of unsold cars that have it, and contact the owners of sold ones.
7. **Noise**: do nothing.
8. **Unclear**: hand it to a person and change nothing.
9. **Completeness**: a real problem should end with at least three kinds of action, unless no customer is owed a loaner.
10. **Do no harm**: never touch anything that was not affected, and practice every action before doing it for real.

---

## 8. Switching the AI model

The AI that reads messages runs on this computer. To switch to a different one:

1. Click the **model button** in the top bar.
2. Pick a model from the list. It switches straight away.
3. To add a new model, someone with access runs a command like `ollama pull llama3.2:3b` on this computer. It will then appear in the list.

Bigger models can read messier messages, but they are slower. The default, Qwen2.5 3B, read all of Monday's messages correctly.

---

## 9. Troubleshooting

| Problem | What to do |
|---|---|
| The model button shows a **red dot** and says **Offline**. | The AI is not running. Ask your system owner to start **Ollama** on this computer. You can still look at everything already handled. You just cannot send new messages until it is back. |
| I sent a message and it came back as **Needs review**, but I think it is real. | The message is probably missing a plant, a part or a date. Add the missing details and send it again. |
| A page looks empty or out of date. | Refresh the page with **Ctrl + R**. |
| The map is zoomed in too far. | Click the **circle** button in the map's corner to reset the view. |
| The tour keeps showing. | Click **Skip**. It only shows once per computer. You can replay it from **Help**. |

---

## 10. Keyboard shortcuts

| Key                 | Where            | What it does                                    |
| ------------------- | ---------------- | ----------------------------------------------- |
| **Esc**             | Anywhere         | Closes a pop-up, a menu or an expanded section. |
| **Enter**           | Incident list    | Opens the selected incident.                    |
| **A**, **E**, **I** | Simulation       | Act, Escalate or Ignore.                        |
| **Enter**           | Simulation       | Next scenario.                                  |
| **Mouse scroll**    | Any map or graph | Zoom in and out.                                |
