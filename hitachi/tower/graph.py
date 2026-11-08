"""The company knowledge graph: build, traverse, fact-check and record provenance."""
import json
from collections import Counter

import networkx as nx

from .types import Downstream, Kind


def nid(kind, key):
    """Graph node id, for example ProductionOrder:PO-0442."""
    return f"{kind}:{key}"


def key(node):
    """Record key of a node id."""
    return node.split(":", 1)[1]


class KnowledgeGraph:
    """NetworkX graph of the company plus Event, Action and Rule nodes."""
    def __init__(self, w):
        self.w = w
        self.g = nx.MultiDiGraph()
        add, rel = self._node, self._edge
        for p, r in w.plants.items():
            add("Plant", p, label=f"{r['city'].split(',')[0]} plant", slots=r["slots"])
            for m in sorted(r["models"]):
                rel(nid("Plant", p), "builds", nid("Model", m))
        for m in w.models:
            add("Model", m, label=m)
            for part in sorted(w.bom[m]):
                rel(nid("Model", m), "contains", nid("Part", part))
        for p, r in w.parts.items():
            add("Part", p, label=r["name"])
        for s, r in w.suppliers.items():
            add("Supplier", s, label=r["name"])
        for d, r in w.dealers.items():
            add("Dealer", d, label=f"{r['name']} ({r['city']})", loaners=w.loaners.get(d, 0))
        for c, r in w.customers.items():
            add("Customer", c, label=r["name"], tier=r["tier"])
        for s, r in w.shipments.items():
            add("Shipment", s, label=s, eta=r["eta_date"])
            rel(nid("Supplier", r["supplier_id"]), "ships", nid("Shipment", s))
            rel(nid("Shipment", s), "carries", nid("Part", r["part_id"]))
            rel(nid("Shipment", s), "delivers_to", nid("Plant", r["plant_id"]))
        for po, r in w.pos.items():
            add("ProductionOrder", po, label=po, model=r["model"], date=r["build_date"], idx=r["idx"])
            rel(nid("ProductionOrder", po), "scheduled_at", nid("Plant", r["plant_id"]))
            rel(nid("ProductionOrder", po), "of_model", nid("Model", r["model"]))
        for co, r in w.cos.items():
            add("CustomerOrder", co, label=co, promised=r["promised_date"])
            rel(nid("ProductionOrder", r["production_order_id"]), "promised_to", nid("CustomerOrder", co))
            rel(nid("CustomerOrder", co), "placed_at", nid("Dealer", r["dealer_id"]))
            rel(nid("CustomerOrder", co), "for", nid("Customer", r["customer_id"]))
        for vin, r in w.vehicles.items():
            add("Vehicle", vin, label=vin, model=r["model"], date=r["build_date"], status=r["status"])
            rel(nid("ProductionOrder", r["production_order_id"]), "produced", nid("Vehicle", vin))
            rel(nid("Vehicle", vin), "stocked_at" if r["status"] == "in_stock" else "sold_by", nid("Dealer", r["dealer_id"]))
            if r["customer_id"]:
                rel(nid("Vehicle", vin), "owned_by", nid("Customer", r["customer_id"]))
        for lot, r in w.lots.items():
            add("Lot", lot, label=lot, first=r["first_build_date"], last=r["last_build_date"])
            rel(nid("Supplier", r["supplier_id"]), "made", nid("Lot", lot))
            rel(nid("Lot", lot), "batch_of", nid("Part", r["part_id"]))
            rel(nid("Lot", lot), "used_at", nid("Plant", r["plant_id"]))
            users = set(w.models_using(r["part_id"]))
            for po, o in w.pos.items():
                if (o["plant_id"] == r["plant_id"] and o["model"] in users
                        and r["first_build_date"] <= o["build_date"] <= r["last_build_date"]):
                    rel(nid("Lot", lot), "installed_in", nid("ProductionOrder", po))
        for n in range(1, 11):
            add("Rule", str(n), label=f"Handbook rule {n}")

    def _node(self, kind, k, **attrs):
        self.g.add_node(nid(kind, k), type=kind, **attrs)

    def _edge(self, u, rel, v):
        self.g.add_edge(u, v, rel=rel)

    def out(self, node, rel):
        """Targets of a node's outgoing edges with this relation."""
        return sorted(v for _, v, d in self.g.out_edges(node, data=True) if d["rel"] == rel)

    def into(self, node, rel):
        """Sources of a node's incoming edges with this relation."""
        return sorted(u for u, _, d in self.g.in_edges(node, data=True) if d["rel"] == rel)

    def one(self, node, rel):
        """The single target of a relation; anything else is a data error."""
        hits = self.out(node, rel)
        if len(hits) != 1:
            raise ValueError(f"{node} has {len(hits)} {rel} edges")
        return hits[0]

    def delay_impact(self, shipment, from_idx, to_idx_excl):
        """Builds that need the delayed part at the receiving plant inside the gap (rule 1)."""
        ship = nid("Shipment", shipment)
        part, plant = self.one(ship, "carries"), self.one(ship, "delivers_to")
        models = [m for m in self.into(part, "contains") if m in self.out(plant, "builds")]
        hits = []
        for po in self.into(plant, "scheduled_at"):
            model = self.one(po, "of_model")
            if model in models and from_idx <= self.g.nodes[po]["idx"] < to_idx_excl and self.g.nodes[po]["idx"] >= 0:
                hits.append((key(po), [ship, part, model, po]))
        return hits

    def outage_impact(self, plant_id, from_idx, to_idx_excl):
        """Builds at the plant inside the outage (rule 2)."""
        plant = nid("Plant", plant_id)
        return [(key(po), [plant, po]) for po in self.into(plant, "scheduled_at")
                if from_idx <= self.g.nodes[po]["idx"] < to_idx_excl and self.g.nodes[po]["idx"] >= 0]

    def orders_downstream(self, po):
        """Customer orders waiting on a build, with dealer and customer."""
        out = []
        for co in self.out(nid("ProductionOrder", po), "promised_to"):
            out.append(Downstream(key(co), key(self.one(co, "placed_at")), key(self.one(co, "for"))))
        return out

    def lot_impact(self, lot_id):
        """Vehicles built with the lot, with dealer and owner (rule 6)."""
        lot = nid("Lot", lot_id)
        vehicles = []
        for po in self.out(lot, "installed_in"):
            for v in self.out(po, "produced"):
                status = self.g.nodes[v]["status"]
                dealer = self.one(v, "stocked_at" if status == "in_stock" else "sold_by")
                owner = self.out(v, "owned_by")
                vehicles.append({"vin": key(v), "status": status, "dealer": key(dealer),
                                 "customer": key(owner[0]) if owner else None, "path": [lot, po, v]})
        return vehicles

    def has(self, u, rel, v):
        """True when the graph holds this exact edge."""
        return self.g.has_node(u) and any(d["rel"] == rel for _, x, d in self.g.out_edges(u, data=True) if x == v)

    def fact_check(self, r):
        """Checks the relationships behind a resolved reading as graph edges."""
        res, kind, claims = r["resolution"], r["kind"], []

        def claim(text, u, rel, v):
            claims.append({"claim": text, "edge": [u, rel, v], "ok": self.has(u, rel, v)})

        plant = nid("Plant", res["plant"]["id"])
        if kind == Kind.SUPPLIER_DELAY:
            s = res["shipment"]
            ship, part = nid("Shipment", s["shipment_id"]), nid("Part", s["part_id"])
            claim("the shipment carries the named part", ship, "carries", part)
            claim("the shipment goes to the named plant", ship, "delivers_to", plant)
            claim("the supplier ships this shipment", nid("Supplier", s["supplier_id"]), "ships", ship)
            for m in r["disruption"]["models"]:
                claim(f"the plant builds {m.title()}", plant, "builds", nid("Model", m))
                claim(f"{m.title()} contains the part", nid("Model", m), "contains", part)
        elif kind == Kind.PLANT_OUTAGE:
            claims.append({"claim": "the plant exists in the network", "edge": [plant], "ok": self.g.has_node(plant)})
        else:
            for lot in res["lots"]:
                node = nid("Lot", lot["lot_id"])
                claim("the lot is a batch of the named part", node, "batch_of", nid("Part", res["part"]["id"]))
                claim("the lot was used at the named plant", node, "used_at", plant)
                claim("the supplier made the lot", nid("Supplier", lot["supplier_id"]), "made", node)
        return claims

    def evidence(self, r):
        """The challenge's required path for an incident, with an example and counts per hop."""
        res, kind = r["resolution"], r["kind"]
        if kind == Kind.QUALITY_HOLD:
            vehicles = [v for lot in res["lots"] for v in self.lot_impact(lot["lot_id"])]
            sold = next((v for v in vehicles if v["customer"]), vehicles[0] if vehicles else None)
            example = sold["path"] + [nid("Dealer", sold["dealer"])] + ([nid("Customer", sold["customer"])] if sold["customer"] else []) if sold else []
            counts = {"Lot": len(res["lots"]), "ProductionOrder": len({v["path"][1] for v in vehicles}), "Vehicle": len(vehicles),
                      "unsold": sum(v["status"] == "in_stock" for v in vehicles), "sold": sum(v["status"] == "sold" for v in vehicles),
                      "Dealer": len({v["dealer"] for v in vehicles}), "Customer": len({v["customer"] for v in vehicles if v["customer"]})}
            return {"required_path": "Lot > ProductionOrder > Vehicle > Dealer / Customer", "example": example, "counts": counts,
                    "fact_check": self.fact_check(r)}
        pos = r.get("affected_production_orders", [])
        down = {po: self.orders_downstream(po) for po in pos}
        head = ([nid("Shipment", res["shipment"]["shipment_id"]), nid("Part", res["shipment"]["part_id"])]
                if kind == Kind.SUPPLIER_DELAY else [nid("Plant", res["plant"]["id"])])
        po = next((p for p in pos if down[p]), pos[0] if pos else None)
        example = head + ([nid("Model", self.w.pos[po]["model"])] if kind == Kind.SUPPLIER_DELAY and po else []) + \
            ([nid("ProductionOrder", po)] if po else []) + \
            ([nid("CustomerOrder", down[po][0].customer_order), nid("Dealer", down[po][0].dealer), nid("Customer", down[po][0].customer)]
             if po and down[po] else [])
        rows = [x for xs in down.values() for x in xs]
        counts = {**({"Shipment": 1, "Part": 1, "Model": len(r["disruption"]["models"])} if kind == Kind.SUPPLIER_DELAY else {"Plant": 1}),
                  "ProductionOrder": len(pos), "CustomerOrder": len(rows), "Dealer": len({r.dealer for r in rows}),
                  "Customer": len({r.customer for r in rows})}
        path = ("Shipment > Part > Model (BOM) > ProductionOrder > CustomerOrder > Dealer / Customer" if kind == Kind.SUPPLIER_DELAY
                else "Plant > ProductionOrder > CustomerOrder > Dealer / Customer")
        return {"required_path": path, "example": example, "counts": counts, "fact_check": self.fact_check(r)}

    def record(self, event_id, n, action):
        """Adds an action node linked to its event, rule and targets."""
        a = nid("Action", f"{event_id}#{n}")
        self._node("Action", f"{event_id}#{n}", label=action["tool"], tool=action["tool"], agent=action["agent"],
                   reason=action["reason"], path=action["path"], event=event_id)
        self._edge(a, "triggered_by", nid("Event", event_id))
        self._edge(a, "applies", nid("Rule", action["rule"]))
        for t in action["targets"]:
            self._edge(a, "acts_on", t)
        return a

    def add_event(self, event_id, text, classification):
        """Adds an event node and clears actions from an earlier run of it."""
        self.g.remove_nodes_from([n for n, d in self.g.nodes(data=True)
                                  if d["type"] == "Action" and d["event"] == event_id])
        self._node("Event", event_id, label=event_id, text=text, classification=classification)

    def why(self, node):
        """Every action that touched a record, with agent, rule and reason."""
        related = {node}
        kind = self.g.nodes[node]["type"]
        if kind == "Customer":
            for co in self.into(node, "for"):
                related |= {co, *self.into(co, "promised_to")}
            related |= set(self.into(node, "owned_by"))
        elif kind == "CustomerOrder":
            related |= set(self.into(node, "promised_to"))
        stories, seen = [], set()
        for t in sorted(related):
            for a in self.into(t, "acts_on"):
                if a in seen:
                    continue
                seen.add(a)
                d = self.g.nodes[a]
                stories.append({"event": d["event"], "action": d["tool"], "agent": d["agent"], "about": t,
                                "rule": key(self.one(a, "applies")), "reason": d["reason"], "path": d["path"]})
        return sorted(stories, key=lambda s: (s["event"], s["action"], s["about"]))

    def ontology(self):
        """Node types and relation types with counts."""
        types = Counter(d["type"] for _, d in self.g.nodes(data=True))
        rels = Counter((self.g.nodes[u]["type"], d["rel"], self.g.nodes[v]["type"])
                       for u, v, d in self.g.edges(data=True))
        return {"node_types": dict(sorted(types.items())),
                "relations": [{"from": a, "rel": r, "to": b, "count": c} for (a, r, b), c in sorted(rels.items())]}

    def mermaid(self):
        """The ontology as a Mermaid diagram."""
        lines = ["graph LR"]
        for r in self.ontology()["relations"]:
            lines.append(f"    {r['from']} -->|{r['rel']}| {r['to']}")
        return "\n".join(lines)

    def export(self, path):
        """Writes the full graph as node-link JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(nx.node_link_data(self.g, edges="edges"), f, default=list)
